"""
External debrid cache checking via third-party APIs and DMM.

RD: DMM /availability/check + Torrentio + AIOStreams + Comet (service-scoped).
AD: DMM /availability/ad/check + Torrentio + AIOStreams + Comet (service-scoped).

Hash results are unioned per debrid. Callers match any scraped torrent hash
(nyaa, torrentio, etc.) against the confirmed set.

DMM is the only hash-list authoritative service: it answers available / not available for
every hash it is sent. Torrentio, Comet and AIOStreams only list hashes from their own
caches, so a hash missing there is no evidence that it is uncached. check_rd_external and
check_ad_external therefore also return the hashes DMM actually answered for.

Every checker returns None when it got no usable answer (exception, non-2xx, error-only
response) and a set (possibly empty) only for a real answer.

Anime episodes may also be looked up by Kitsu id (``kitsu:<id>:<episode>``), which
Torrentio/Comet/AIOStreams use for anime; DMM is IMDb-only.
"""
from __future__ import annotations

import base64
import datetime
import json
import random
import re
import threading
import time
from collections import namedtuple
from concurrent.futures import ThreadPoolExecutor, wait

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from resources.lib.modules.globals import g

_BROWSER_UAS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:151.0) Gecko/20100101 Firefox/151.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36 Edg/148.0.0.0",
]

_session = None

_TIO_BASE = "https://torrentio.strem.fun"
_TIO_FALLBACK_PARAM = "realdebrid=T2iZoymNCCD1T5c2sX5u8tIZVcgcFWlCsCJ72rCmrU2mDdmvgieM"
_TIO_OPTIONS = "debridoptions=nodownloadlinks,nocatalog"
_HASH_PATTERN = re.compile(r"\b[a-fA-F0-9]{40}\b")
_TIO_TIMEOUT = 8
_TIO_SERVICE_PARAM = {"rd": "realdebrid", "ad": "alldebrid"}

_DMM_URL_RD = "https://debridmediamanager.com/api/availability/check"
_DMM_URL_AD = "https://debridmediamanager.com/api/availability/ad/check"
_DMM_CHALLENGE_URL = "https://debridmediamanager.com/api/challenge"
_DMM_TIMEOUT = 8
# DMM mints availability tokens server-side (GET /api/challenge -> {token, hash}, 5 min
# server TTL, IP rate limited). Its own web client reuses a token for 2 min; stay below that.
_DMM_TOKEN_REUSE_SECONDS = 110
# After a failed challenge fetch, fail fast instead of asking again for every provider batch.
_DMM_CHALLENGE_RETRY_SECONDS = 30
_DMM_CHUNK_SIZE = 100  # DMM rejects more than 100 hashes per request
_DMM_HASH_PATTERN = re.compile(r"^[a-fA-F0-9]{40}$")
_DMM_IMDB_PATTERN = re.compile(r"^tt\d+$")

_dmm_token_lock = threading.Lock()
_dmm_token = None  # (token, signature, reuse_until) with reuse_until on time.monotonic()
_dmm_challenge_failed_until = 0.0

# DMM's answer for one batch: the lowercase hashes it reported available (cached) and every
# lowercase hash it answered for (checked).
_DmmAnswer = namedtuple("_DmmAnswer", "cached checked")

_AIO_URLS = [
    "https://aiostreams.fortheweak.cloud/api/v1/search",
    "https://aiostreams.stremio.ru/api/v1/search",
]
_AIO_TIMEOUT = 8
_AIO_AD_DEMO_KEY = "staticDemoApikeyPrem"

_AIO_PRESETS = [
    {
        "type": "mediafusion",
        "instanceId": "5b8",
        "enabled": True,
        "options": {
            "name": "MediaFusion",
            "timeout": 6500,
            "resources": ["stream"],
            "useCachedResultsOnly": True,
            "enableWatchlistCatalogs": False,
            "downloadViaBrowser": False,
            "contributorStreams": False,
            "certificationLevelsFilter": [],
            "nudityFilter": [],
            "mediaTypes": [],
        },
    },
    {
        "type": "stremthruTorz",
        "instanceId": "548",
        "enabled": True,
        "options": {
            "name": "StremThru Torz",
            "timeout": 6500,
            "resources": ["stream"],
            "mediaTypes": [],
            "includeP2P": False,
            "useMultipleInstances": False,
        },
    },
]

_AIO_STATIC_CONFIG = {
    "formatter": {"id": "torrentio", "definition": {"name": "", "description": ""}},
    "sortCriteria": {"global": []},
    "deduplicator": {
        "enabled": False,
        "keys": ["infoHash"],
        "multiGroupBehaviour": "aggressive",
        "cached": "single_result",
        "uncached": "per_service",
        "p2p": "single_result",
        "excludeAddons": [],
    },
    "excludeUncached": True,
}

_COMET_BASES = [
    "https://comet.feels.legal",
    "https://comet.stremio.ru",
    "https://cometfortheweebs.midnightignite.me",
]
_COMET_SERVICE_MAP = {"ad": "alldebrid", "rd": "realdebrid"}
_COMET_ERROR_NAME_PREFIX = "[❌"  # "[❌] realdebrid" error streams
_COMET_ERROR_TEXT = "invalid api key"
_DIRECT_TIMEOUT = 10

_KITSU_MAPPING_URLS = (
    "https://kitsu.app/api/edge/mappings",
    "https://kitsu.io/api/edge/mappings",
)
_KITSU_TIMEOUT = 3
# Upper bound (seconds) for one resolve_kitsu_id() call, all hosts and ids included.
KITSU_LOOKUP_BUDGET = 5
_KITSU_CACHE_HOURS = 168
_KITSU_NEGATIVE_CACHE_HOURS = 24
_KITSU_PREFIX = "kitsu:"

# Short-lived memo of real answers, so the per-provider cache checks of one scrape share them
# (anime with IMDb + Kitsu otherwise costs ~7 requests per provider batch).
_MEMO_TTL_SECONDS = 60
_MEMO_PRUNE_SIZE = 2000
_memo_lock = threading.Lock()
_memo = {}
_MISSING = object()

# A failed RD token refresh is not retried for this long (every provider batch checks).
_RD_REFRESH_RETRY_SECONDS = 300
_rd_refresh_lock = threading.Lock()
_rd_refresh_failed_at = None

_URL_IN_ERROR = re.compile(r"(url: )\S+")


def _get_session():
    global _session
    if _session is None:
        _session = requests.Session()
        retries = Retry(total=2, backoff_factor=0.2, status_forcelist=[500, 502, 503])
        _session.mount("https://", HTTPAdapter(max_retries=retries))
        _session.headers.update({
            "User-Agent": random.choice(_BROWSER_UAS),
            "Accept": "application/json",
        })
    return _session


def _describe_error(exc):
    """Log-safe error text: request URLs can carry debrid keys (Torrentio, Comet config)."""
    response = getattr(exc, "response", None)
    if response is not None and getattr(response, "status_code", None):
        return f"HTTP {response.status_code}"
    return _URL_IN_ERROR.sub(r"\1<redacted>", str(exc))


def _memo_get(key):
    with _memo_lock:
        entry = _memo.get(key)
        if entry is None:
            return _MISSING
        if entry[0] <= time.monotonic():
            _memo.pop(key, None)
            return _MISSING
        return entry[1]


def _memo_set_many(items):
    now = time.monotonic()
    with _memo_lock:
        if len(_memo) >= _MEMO_PRUNE_SIZE:
            for key in [key for key, entry in _memo.items() if entry[0] <= now]:
                del _memo[key]
            if len(_memo) >= _MEMO_PRUNE_SIZE:
                _memo.clear()
        for key, value in items:
            _memo[key] = (now + _MEMO_TTL_SECONDS, value)


def _memoised(key, call):
    """Run checker ``call`` unless a real answer for ``key`` is memoised; None is never kept."""
    value = _memo_get(key)
    if value is not _MISSING:
        g.log(f"ExternalCache: reusing {key[0]} {key[1].upper()} answer for {key[2]} ({len(value)} cached hashes)")
        return set(value)
    result = call()
    if result is not None:
        _memo_set_many([(key, frozenset(result))])
    return result


def _stremio_stream_id(media_id, season, episode):
    """
    Return (type, id) for a Stremio stream request.

    IMDb ids keep the ``tt...:season:episode`` / ``tt...`` shape. Anime may pass a
    ``kitsu:<id>`` media id, which is addressed as ``kitsu:<id>:<episode>`` (Kitsu
    numbers episodes per entry, there is no season component).
    """
    media_id = str(media_id)
    if media_id.startswith(_KITSU_PREFIX):
        if episode is not None and str(episode).isdigit():
            return "series", f"{media_id}:{episode}"
        return "movie", media_id
    if season is not None and str(season).isdigit():
        return "series", f"{media_id}:{season}:{episode}"
    return "movie", media_id


def _extract_hashes_from_streams(streams):
    hashes = set()
    for stream in streams:
        info_hash = stream.get("infoHash", "")
        if info_hash and len(info_hash) == 40:
            hashes.add(info_hash.lower())
            continue
        stream_url = stream.get("url", "")
        if stream_url:
            matches = _HASH_PATTERN.findall(stream_url)
            if matches:
                hashes.add(matches[-1].lower())
    return hashes


def _get_torrentio_debrid_param(service, debrid_key):
    svc = (service or "rd").lower()
    if debrid_key:
        param_name = _TIO_SERVICE_PARAM.get(svc, "realdebrid")
        return f"{param_name}={debrid_key}"
    if svc == "rd":
        return _TIO_FALLBACK_PARAM
    return None


def torrentio_check_cache(imdb, season, episode, service="rd", debrid_key=None):
    """Hashes Torrentio lists as cached ("+" in the name), set() if none, None on failure."""
    if not imdb:
        return None

    stream_type, stream_id = _stremio_stream_id(imdb, season, episode)
    path = f"{stream_type}/{stream_id}.json"

    debrid_param = _get_torrentio_debrid_param(service, debrid_key)
    if not debrid_param:
        return None

    hashes = set()
    try:
        url = f"{_TIO_BASE}/{_TIO_OPTIONS}|{debrid_param}/stream/{path}"
        resp = _get_session().get(url, timeout=_TIO_TIMEOUT)
        resp.raise_for_status()
        streams = resp.json().get("streams")
        if not isinstance(streams, list):
            raise ValueError("response has no 'streams' list")
        for stream in streams:
            if "+" not in stream.get("name", ""):
                continue
            info_hash = stream.get("infoHash", "")
            if info_hash and len(info_hash) == 40:
                hashes.add(info_hash.lower())
                continue
            stream_url = stream.get("url", "")
            if stream_url:
                matches = _HASH_PATTERN.findall(stream_url)
                if matches:
                    hashes.add(matches[-1].lower())
    except Exception as exc:
        g.log(f"ExternalCache: Torrentio check failed ({service}): {_describe_error(exc)}", "warning")
        return None
    g.log(
        f"ExternalCache: Torrentio ({_TIO_BASE}) returned {len(hashes)} cached hashes "
        f"for {(service or 'rd').upper()}",
        "info",
    )
    return hashes


def _dmm_get_challenge(force=False, failed_token=None):
    """
    (token, signature) for DMM's availability endpoints, sent as dmmProblemKey / solution.
    Minted server-side by GET /api/challenge and shared by all threads for
    _DMM_TOKEN_REUSE_SECONDS. ``force`` fetches a new one, unless another thread already
    replaced ``failed_token``. Raises when no token could be obtained.
    """
    global _dmm_token, _dmm_challenge_failed_until
    with _dmm_token_lock:
        now = time.monotonic()
        cached = _dmm_token
        if cached and cached[2] > now:
            if not force or (failed_token is not None and cached[0] != failed_token):
                return cached[0], cached[1]
        _dmm_token = None
        if now < _dmm_challenge_failed_until:
            raise RuntimeError("DMM challenge failed recently, not retrying yet")
        try:
            resp = _get_session().get(_DMM_CHALLENGE_URL, timeout=_DMM_TIMEOUT)
            resp.raise_for_status()
            payload = resp.json()
            token = payload.get("token") if isinstance(payload, dict) else None
            signature = payload.get("hash") if isinstance(payload, dict) else None
            if not token or not signature or not isinstance(token, str) or not isinstance(signature, str):
                raise ValueError("malformed DMM challenge response")
        except Exception as exc:
            _dmm_challenge_failed_until = time.monotonic() + _DMM_CHALLENGE_RETRY_SECONDS
            raise RuntimeError(f"DMM challenge failed: {_describe_error(exc)}") from exc
        _dmm_token = (token, signature, time.monotonic() + _DMM_TOKEN_REUSE_SECONDS)
        return token, signature


def _dmm_post_chunk(url, imdb, chunk):
    """Lowercase hashes DMM reports available among ``chunk``. Raises when DMM did not answer."""

    def post(token, signature):
        payload = {"dmmProblemKey": token, "solution": signature, "imdbId": imdb, "hashes": chunk}
        return _get_session().post(url, json=payload, timeout=_DMM_TIMEOUT)

    token, signature = _dmm_get_challenge()
    resp = post(token, signature)
    if resp.status_code == 403:
        # Token expired or rejected: mint a new one once and retry.
        token, signature = _dmm_get_challenge(force=True, failed_token=token)
        resp = post(token, signature)
    resp.raise_for_status()
    available = resp.json().get("available")
    if not isinstance(available, list):
        raise ValueError("response has no 'available' list")
    return {
        item["hash"].lower()
        for item in available
        if isinstance(item, dict) and isinstance(item.get("hash"), str) and item["hash"]
    }


def _dmm_check(hashes, imdb, service):
    """
    Ask DMM which ``hashes`` are available on RD (service "rd") or AD ("ad") for ``imdb``.
    Hashes go out in chunks of _DMM_CHUNK_SIZE; answers are memoised for _MEMO_TTL_SECONDS.
    Returns _DmmAnswer(cached, checked), or None when DMM answered for no hash at all.
    """
    if not imdb or not _DMM_IMDB_PATTERN.match(str(imdb)):
        return None
    valid_hashes = list(dict.fromkeys(
        info_hash.lower()
        for info_hash in hashes or ()
        if isinstance(info_hash, str) and _DMM_HASH_PATTERN.match(info_hash)
    ))
    if not valid_hashes:
        return None

    label = "RD" if service == "rd" else "AD"
    url = _DMM_URL_RD if service == "rd" else _DMM_URL_AD
    cached, checked, pending = set(), set(), []
    for info_hash in valid_hashes:
        known = _memo_get(("dmm", service, imdb, info_hash))
        if known is _MISSING:
            pending.append(info_hash)
            continue
        checked.add(info_hash)
        if known:
            cached.add(info_hash)

    for index in range(0, len(pending), _DMM_CHUNK_SIZE):
        chunk = pending[index:index + _DMM_CHUNK_SIZE]
        try:
            available = _dmm_post_chunk(url, imdb, chunk)
        except Exception as exc:
            g.log(f"ExternalCache: DMM {label} check failed: {_describe_error(exc)}", "warning")
            break  # the remaining chunks would fail the same way
        _memo_set_many([(("dmm", service, imdb, info_hash), info_hash in available) for info_hash in chunk])
        checked.update(chunk)
        cached.update(info_hash for info_hash in chunk if info_hash in available)

    if not checked:
        return None
    g.log(
        f"ExternalCache: DMM {label} returned {len(cached)} cached hashes "
        f"(checked {len(checked)} of {len(valid_hashes)})",
        "info",
    )
    return _DmmAnswer(cached, checked)


def _dmm_check_cache(hashes, imdb, service):
    """Hashes DMM reports cached, set() if none, None when DMM gave no answer."""
    answer = _dmm_check(hashes, imdb, service)
    return None if answer is None else answer.cached


def dmm_check_cache_rd(hashes, imdb):
    return _dmm_check_cache(hashes, imdb, "rd")


def dmm_check_cache_ad(hashes, imdb):
    return _dmm_check_cache(hashes, imdb, "ad")


def _build_aio_user_data(service, api_key):
    svc = (service or "ad").lower()
    if svc == "ad":
        key = api_key or _AIO_AD_DEMO_KEY
        services = [{"id": "alldebrid", "enabled": True, "credentials": {"apiKey": key}}]
    elif svc == "rd":
        if not api_key:
            return None
        services = [{"id": "realdebrid", "enabled": True, "credentials": {"apiKey": api_key}}]
    else:
        return None
    payload = {"services": services, "presets": _AIO_PRESETS, **_AIO_STATIC_CONFIG}
    return base64.b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode()


def aio_check_cache(imdb, season, episode, service="ad", api_key=None):
    """Hashes AIOStreams lists as cached, set() if none, None when no instance answered."""
    if not imdb:
        return None

    stream_type, stream_id = _stremio_stream_id(imdb, season, episode)
    params = {"type": stream_type, "id": stream_id}

    user_data = _build_aio_user_data(service, api_key)
    if not user_data:
        return None

    headers = {"x-aiostreams-user-data": user_data}
    for url in _AIO_URLS:
        try:
            resp = _get_session().get(url, params=params, headers=headers, timeout=_AIO_TIMEOUT)
            resp.raise_for_status()
            payload = resp.json()
            if payload.get("success") is False:
                raise ValueError(f"error response: {str(payload.get('error'))[:120]}")
            results = (payload.get("data") or {}).get("results")
            if not isinstance(results, list):
                raise ValueError("response has no 'data.results' list")
            hashes = set()
            for item in results:
                info_hash = item.get("infoHash", "")
                if info_hash:
                    hashes.add(info_hash.lower())
            g.log(
                f"ExternalCache: AIOStreams ({url}) returned {len(hashes)} cached hashes "
                f"for {(service or 'ad').upper()}",
                "info",
            )
            return hashes
        except Exception as exc:
            g.log(f"ExternalCache: AIOStreams failed ({url}): {_describe_error(exc)}", "warning")
    return None


def _build_comet_config(api_key, service="ad"):
    comet_service = _COMET_SERVICE_MAP.get(service, "alldebrid")
    payload = {
        "maxResultsPerResolution": 0,
        "maxSize": 0,
        "cachedOnly": True,
        "removeTrash": True,
        "resultFormat": ["title", "metadata"],
        "debridService": comet_service,
        "debridApiKey": api_key,
        "debridStreamProxyPassword": "",
        "languages": {"required": [], "exclude": [], "preferred": []},
        "resolutions": {},
        "options": {
            "remove_ranks_under": -10000000000,
            "allow_english_in_languages": False,
            "remove_unknown_languages": False,
        },
    }
    return base64.b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode()


def _is_comet_error_stream(stream):
    """Comet reports problems (e.g. an invalid debrid key) as a 200 with a "[❌] ..." stream."""
    if not isinstance(stream, dict):
        return True
    text = f"{stream.get('title') or ''} {stream.get('description') or ''}".lower()
    return str(stream.get("name") or "").startswith(_COMET_ERROR_NAME_PREFIX) or _COMET_ERROR_TEXT in text


def comet_check_cache(imdb, season, episode, api_key=None, service="ad"):
    """
    Hashes Comet lists as cached, set() if none, None when no instance gave a real answer.
    An instance that answers 200 with only error streams (or none plus an error) is skipped.
    """
    if not imdb:
        return None

    svc = (service or "ad").lower()
    key = api_key or (_AIO_AD_DEMO_KEY if svc == "ad" else None)
    if not key:
        return None

    stream_type, stream_id = _stremio_stream_id(imdb, season, episode)
    path = f"stream/{stream_type}/{stream_id}.json"

    config = _build_comet_config(key, svc)
    for base in _COMET_BASES:
        try:
            url = f"{base}/{config}/{path}"
            resp = _get_session().get(url, timeout=_DIRECT_TIMEOUT)
            resp.raise_for_status()
            payload = resp.json()
            streams = payload.get("streams")
            if not isinstance(streams, list):
                raise ValueError("response has no 'streams' list")
            real_streams = [stream for stream in streams if not _is_comet_error_stream(stream)]
            if not real_streams and (streams or any(payload.get(k) for k in ("error", "detail", "message"))):
                error_stream = next((stream for stream in streams if isinstance(stream, dict)), {})
                detail = error_stream.get("description") or error_stream.get("title") or payload.get("error") or ""
                raise ValueError(f"error-only answer: {' '.join(str(detail).split())[:120]}")
            hashes = _extract_hashes_from_streams(real_streams)
            g.log(
                f"ExternalCache: Comet ({base}) returned {len(hashes)} cached hashes for {svc.upper()}",
                "info",
            )
            return hashes
        except Exception as exc:
            g.log(f"ExternalCache: Comet failed ({base}): {_describe_error(exc)}", "warning")
    return None


def _run_parallel_checks(futures_map, label, timeout=12):
    """
    Run the checkers in parallel. Returns (cached, success, dmm_checked):
    success is True when something is cached, None when at least one checker gave a real
    answer but nothing is cached, False when no checker gave a usable answer (all None or
    raised). dmm_checked holds the hashes DMM answered for.
    """
    all_cached = set()
    dmm_checked = set()
    answered = 0
    with ThreadPoolExecutor(max_workers=len(futures_map)) as executor:
        futures = {executor.submit(fn): name for name, fn in futures_map.items()}
        _done, not_done = wait(futures, timeout=timeout)
        if not_done:
            pending = ", ".join(sorted(futures[future] for future in not_done))
            g.log(f"ExternalCache {label}: still waiting after {timeout}s for {pending}", "warning")
    # Leaving the executor waits for every check, so late answers are used as well.
    for future, name in futures.items():
        try:
            result = future.result()
        except Exception as exc:
            g.log(f"ExternalCache {label}: {name} thread error: {exc}", "warning")
            continue
        if result is None:
            continue
        answered += 1
        if isinstance(result, _DmmAnswer):
            all_cached.update(result.cached)
            dmm_checked.update(result.checked)
        else:
            all_cached.update(result)

    if all_cached:
        return all_cached, True, dmm_checked
    if answered > 0:
        return all_cached, None, dmm_checked
    return all_cached, False, dmm_checked


def _memoised_future(checker, service, media_id, season, episode, key, call):
    memo_key = (checker, service, str(media_id), str(season), str(episode), key or "")
    return lambda: _memoised(memo_key, call)


def _rd_check_futures(hash_list, imdb, season, episode, rd_token, label=""):
    futures_map = {}
    if not str(imdb).startswith(_KITSU_PREFIX):
        futures_map[f"dmm{label}"] = lambda: _dmm_check(hash_list, imdb, "rd")
    ctx = ("rd", imdb, season, episode, rd_token)
    futures_map[f"torrentio{label}"] = _memoised_future(
        "torrentio", *ctx, lambda: torrentio_check_cache(imdb, season, episode, "rd", rd_token)
    )
    futures_map[f"comet{label}"] = _memoised_future(
        "comet", *ctx, lambda: comet_check_cache(imdb, season, episode, rd_token, "rd")
    )
    if rd_token:
        futures_map[f"aiostreams{label}"] = _memoised_future(
            "aiostreams", *ctx, lambda: aio_check_cache(imdb, season, episode, "rd", rd_token)
        )
    return futures_map


def _extra_context_futures(build_futures, hash_list, extra_contexts, key):
    futures_map = {}
    for media_id, season, episode in extra_contexts or ():
        if media_id:
            futures_map.update(build_futures(hash_list, media_id, season, episode, key, f" ({media_id})"))
    return futures_map


def _refresh_rd_token_if_expired():
    """
    Refresh an expired RD OAuth token before it is handed to Torrentio / Comet / AIOStreams
    (maintenance refreshes only every ~15 min). RealDebrid.try_refresh_token() is called
    non-forced, so a still valid token is left alone.
    """
    global _rd_refresh_failed_at
    with _rd_refresh_lock:
        if _rd_refresh_failed_at is not None and time.monotonic() - _rd_refresh_failed_at < _RD_REFRESH_RETRY_SECONDS:
            return
        try:
            if not g.get_setting("rd.refresh") or (g.get_float_setting("rd.expiry") or 0) > time.time():
                return
            from resources.lib.debrid import real_debrid  # local import: real_debrid pulls in a lot

            if real_debrid.RealDebrid().try_refresh_token() is False:
                _rd_refresh_failed_at = time.monotonic()
                g.log("ExternalCache RD: expired token could not be refreshed", "warning")
            else:
                g.log("ExternalCache RD: refreshed expired token before the cache check", "info")
        except Exception as exc:
            _rd_refresh_failed_at = time.monotonic()
            g.log(f"ExternalCache RD: token refresh failed: {_describe_error(exc)}", "warning")


def check_rd_external(hash_list, imdb, season, episode, extra_contexts=None):
    """
    :param extra_contexts: optional extra (media_id, season, episode) lookups unioned with
        the IMDb one, e.g. ``("kitsu:46474", None, "5")`` for anime episodes.
    :return: (cached_hashes, success, dmm_checked_hashes), all hashes lowercase.
        success: True = something cached, None = answered but nothing cached, False = no
        service answered. dmm_checked_hashes: the hashes DMM answered for; only these are
        verified, any other hash missing from cached_hashes is merely unconfirmed.
    """
    _refresh_rd_token_if_expired()
    rd_token = g.get_setting("rd.auth")
    futures_map = _rd_check_futures(hash_list, imdb, season, episode, rd_token) if imdb else {}
    futures_map.update(_extra_context_futures(_rd_check_futures, hash_list, extra_contexts, rd_token))
    if not futures_map:
        return set(), False, set()
    cached, success, dmm_checked = _run_parallel_checks(futures_map, "RD")
    g.log(
        f"ExternalCache RD: {len(cached)} total cached hashes "
        f"(DMM answered for {len(dmm_checked)} of {len(hash_list)})",
        "info",
    )
    return cached, success, dmm_checked


_AD_PRIME_IMDB = "tt0111161"


def prime_ad_cache_checker_devices():
    """
    Contact Torrentio, AIOStreams, and Comet with the user's AllDebrid key.

    This does not approve devices automatically — it triggers AllDebrid's pending
    device/location prompts so they appear on alldebrid.com/magnets/ right after PIN auth.
    """
    ad_key = (g.get_setting("alldebrid.apikey") or "").strip()
    if not ad_key:
        return
    futures_map = {
        "torrentio": lambda: torrentio_check_cache(_AD_PRIME_IMDB, None, None, "ad", ad_key),
        "aiostreams": lambda: aio_check_cache(_AD_PRIME_IMDB, None, None, "ad", ad_key),
        "comet": lambda: comet_check_cache(_AD_PRIME_IMDB, None, None, ad_key, "ad"),
    }
    _run_parallel_checks(futures_map, "AD-prime", timeout=12)
    g.log("ExternalCache AD: primed cache checker device approval requests", "info")


def _ad_check_futures(hash_list, imdb, season, episode, ad_key, label=""):
    futures_map = {}
    if not str(imdb).startswith(_KITSU_PREFIX):
        futures_map[f"dmm{label}"] = lambda: _dmm_check(hash_list, imdb, "ad")
    ctx = ("ad", imdb, season, episode, ad_key)
    futures_map[f"torrentio{label}"] = _memoised_future(
        "torrentio", *ctx, lambda: torrentio_check_cache(imdb, season, episode, "ad", ad_key)
    )
    futures_map[f"aiostreams{label}"] = _memoised_future(
        "aiostreams", *ctx, lambda: aio_check_cache(imdb, season, episode, "ad", ad_key)
    )
    futures_map[f"comet{label}"] = _memoised_future(
        "comet", *ctx, lambda: comet_check_cache(imdb, season, episode, ad_key or None, "ad")
    )
    return futures_map


def check_ad_external(hash_list, imdb, season, episode, extra_contexts=None):
    """
    :param extra_contexts: optional extra (media_id, season, episode) lookups unioned with
        the IMDb one, e.g. ``("kitsu:46474", None, "5")`` for anime episodes.
    :return: (cached_hashes, success, dmm_checked_hashes), same contract as check_rd_external.
    """
    ad_key = g.get_setting("alldebrid.apikey")
    futures_map = _ad_check_futures(hash_list, imdb, season, episode, ad_key) if imdb else {}
    futures_map.update(_extra_context_futures(_ad_check_futures, hash_list, extra_contexts, ad_key))
    if not futures_map:
        return set(), False, set()
    cached, success, dmm_checked = _run_parallel_checks(futures_map, "AD", timeout=30)
    g.log(
        f"ExternalCache AD: {len(cached)} total cached hashes "
        f"(DMM answered for {len(dmm_checked)} of {len(hash_list)})",
        "info",
    )
    return cached, success, dmm_checked


def _kitsu_mapping_lookup(external_site, external_id, deadline):
    """
    Kitsu anime id for an external (MAL / AniList) anime id, or "" when Kitsu has no mapping.
    One plain request per host (no retry adapter), each bounded by ``deadline``
    (time.monotonic()). Raises when no host answered.
    """
    params = {
        "filter[externalSite]": external_site,
        "filter[externalId]": str(external_id),
        "include": "item",
        "fields[anime]": "slug",
    }
    headers = {"User-Agent": random.choice(_BROWSER_UAS), "Accept": "application/vnd.api+json"}
    last_exc = TimeoutError("Kitsu lookup time budget exhausted")
    for url in _KITSU_MAPPING_URLS:
        remaining = deadline - time.monotonic()
        if remaining <= 0.5:
            break
        try:
            resp = requests.get(url, params=params, headers=headers, timeout=min(_KITSU_TIMEOUT, remaining))
            resp.raise_for_status()
            for mapping in resp.json().get("data", []):
                item = ((mapping.get("relationships") or {}).get("item") or {}).get("data") or {}
                if item.get("type") == "anime" and str(item.get("id", "")).isdigit():
                    return str(item["id"])
            return ""
        except Exception as exc:
            last_exc = exc
    raise last_exc


def _kitsu_cache_get(cache_key):
    try:
        from resources.lib.database.cache import CacheBase

        value = g.CACHE.get(cache_key)
        return None if value == CacheBase.NOT_CACHED else value
    except Exception:
        return None


def _kitsu_cache_set(cache_key, kitsu_id):
    # "No mapping" is cached for a day only: airing shows often get their Kitsu mapping later.
    hours = _KITSU_CACHE_HOURS if kitsu_id else _KITSU_NEGATIVE_CACHE_HOURS
    try:
        g.CACHE.set(cache_key, kitsu_id, expiration=datetime.timedelta(hours=hours))
    except Exception:
        pass


def resolve_kitsu_id(mal_id=None, anilist_id=None):
    """
    Map MAL / AniList anime ids to a Kitsu id. Torrentio and Comet address anime by
    ``kitsu:<id>`` when there is no (or no matching) IMDb id. Returns None when unknown or
    when Kitsu did not answer within KITSU_LOOKUP_BUDGET seconds (failures are not cached).
    """
    deadline = time.monotonic() + KITSU_LOOKUP_BUDGET
    for external_site, external_id in (("myanimelist/anime", mal_id), ("anilist/anime", anilist_id)):
        if external_id in (None, "", 0):
            continue
        cache_key = f"external_cache.kitsu_mapping.{external_site}.{external_id}"
        kitsu_id = _kitsu_cache_get(cache_key)
        if kitsu_id is None:
            try:
                kitsu_id = _kitsu_mapping_lookup(external_site, str(external_id), deadline)
            except Exception as exc:
                g.log(f"ExternalCache: Kitsu mapping lookup failed ({external_site} {external_id}): {exc}", "warning")
                return None
            _kitsu_cache_set(cache_key, kitsu_id)
        if kitsu_id:
            return kitsu_id
    return None
