# Prism 5.0.57: every Real-Debrid torrent shown as uncached (DMM auth broken)

> Investigation and fix of 2026-10-06, released as plugin.video.prism 5.0.58 (commit pending).
> Follow-up to `docs/anime-rd-cache-investigation.md` (5.0.57), which did **not** fix this case.
> Paths are relative to `plugin.video.prism/resources/lib/`. "HEAD:n" is a line in c28dfbe
> (5.0.57). The fixed code is cited by function name. Open items are tracked in `.wolf/STATUS.md`.

## (a) Symptom
- *Lord of Mysteries* S01E01 (2025 donghua; IMDb tt28618556, Kitsu 48233, MAL 49818, AniList 137667).
- Prism 5.0.57 listed every Real-Debrid (RD) torrent as uncached. Seren 3.0.62, using the same
  a4kScrapers torrentio scraper, listed many as cached.
- The a4k torrentio filter (title-anchored `s01e01`) keeps the 17 `S01E01 ... CR WEB-DL`-style
  single-episode releases and drops `- 01v3` names and most batches.

## (b) Traced flow (getSources.py unless noted)
- `Sources._get_provider_sources` (HEAD:567-636) calls `provider.episode(simple_info, info)` without
  `apikeys` (HEAD:586). a4k therefore queries Torrentio without a key and gets no `[RD+]` markers.
- `_process_torrent_source` (HEAD:638-651) keeps the scraper keys. Torrents go to `allTorrents` and
  to `TorrentCacheCheck.torrent_cache_check` (HEAD:1383-1407).
- `_init_db_cache_rows` / `_split_by_db_cache` (HEAD:1295-1320): a hash with any non-expired
  debridCache row counts as "known". Only `"True"` rows are stored as cached.
- `_realdebrid_worker` (HEAD:1442-1484) honours only `rd_cached` (HEAD:1453), which no scraper sets.
  It then calls `external_cache.check_rd_external` (HEAD:1462-1468) with an IMDb context and a Kitsu context.
- `check_rd_external` (`debrid/external_cache.py` HEAD:462-476) runs DMM (IMDb only), Torrentio, Comet and
  AIOStreams in a single `_run_parallel_checks` call (HEAD:408-440, 12 s timeout).
- `_write_cache_results` (HEAD:1322-1337) writes every unconfirmed hash as `"False"`. Those rows live
  4 h (`database/debridCache/__init__.py` HEAD:10-11).
- `_finalise_results` (HEAD:326-352): anything not in `cached_hashes` is shown as uncached.

**Only DMM checks an arbitrary list of hashes.** Torrentio, Comet and AIOStreams return only the
hashes in their own crowd caches for that id. For this title those caches know only SubsPlease
and batch releases, and none of the 17 `S01E01` releases.

## (c) Root causes
1. **DMM authentication broken since 2026-08-31 (certain, verified live).**
   - `_dmm_get_secret` (external_cache.py HEAD:251-257) signed the token on the client with a hard-coded
     salt. DMM moved signing to the server (DMM upstream commit dd6ff80920). Clients now call
     `GET /api/challenge` and get `{token, hash}` back. The token lives 5 min on the server, and
     the endpoint is rate-limited per IP.
   - Every call returned `403 {"errorMessage":"Authentication error"}`, for RD and AD and for any
     IMDb id (control: tt0111161). `_dmm_check_cache` (HEAD:260-294) swallowed the error and returned `set()`.
   - The breakage is global. Movies and TV lost DMM too, which the crowd caches hide for mainstream titles.
   - Only the first 100 hashes were ever sent (HEAD:266-267).
2. **Failed checks were persisted as uncached (certain, code logic).**
   - Each checker returned `set()` on error. `_run_parallel_checks` still counted that as a run
     (HEAD:420/432), so "failed" looked the same as "nothing cached".
   - `_realdebrid_worker` wrote every unconfirmed hash as `"False"` for 4 h (HEAD:1480). It did
     this even when `success is False`.
   - The ce0d509 unverified fallback (HEAD:1476) fires only when there is no IMDb id and no Kitsu id.
     This title has both.
3. **Stale negatives (likely contributor; cannot verify without the user's DB).**
   - `"False"` rows from 5.0.56 and 5.0.57 runs leave `needs_check` empty, so neither the external
     call nor the fallback runs until the rows expire.
   - The torrentCache replay (HEAD:423-432) feeds the same hashes back in.
4. **Minor.**
   - Comet (HEAD:376-405) stopped at the first base that answered 2xx (break at HEAD:402), even when
     that answer was only an "Invalid API key" error stream.
   - `rd.auth` was read raw (HEAD:467), so an expired token was used as is.
   - `aiostreams.vortetos.com` (HEAD:51) no longer resolves in DNS.
   - `_split_by_db_cache` compared hashes case-sensitively.
   - Scraper `debrid == "RD"/"AD"` markers were ignored.
   - Log lines contained URLs that embed keys.

**Ruled out:** "Prism drops a scraper-provided `debrid_provider`". The a4k torrentio scraper never
sets that key. It sets `debrid='RD'` only when it receives `apikeys`, and neither addon passes them.

## (d) What Seren 3.0.62 actually does
- `_realdebrid_worker` (`upstream/update` getSources.py:1164-1170) sets
  `debrid_provider='real_debrid'` on **every** scraped torrent and stores it, with no check. The key
  order in the user's log dict confirms it: `debrid_provider` comes last, added after processing.
- The resolver verifies on play (`RealDebrid.check_hash`). Seren's own kodi.log shows
  "Failed to resolve source" for these "cached" torrents.
- So Seren's "cached" really means "scraped". Prism reported those torrents truthfully, but it was
  blind to the releases that only DMM knows.

## (e) Fix (5.0.58)
- `debrid/external_cache.py`:
  - `_dmm_get_challenge` fetches the token from `/api/challenge` and shares it across threads under a lock.
    - The token is reused for 110 s.
    - On a 403, `_dmm_post_chunk` fetches a fresh token once and retries.
    - After a failed challenge it backs off for 30 s.
  - Client-side signing is removed.
  - `_dmm_check` sends the hashes in chunks of 100 and returns both the cached hashes and the hashes DMM answered for.
  - Checkers return `None` when there is no answer and `set()` only for a real answer.
    `check_rd_external` / `check_ad_external` return `(cached, success, dmm_checked)`.
  - Comet: `_is_comet_error_stream` skips bases that return only error streams.
  - `_refresh_rd_token_if_expired` runs before `rd.auth` is read.
  - The vortetos URL is removed.
  - External answers are memoised for 60 s per scrape (`_memoised`).
  - `_describe_error` redacts URLs in log lines.
- `modules/getSources.py`:
  - `_write_cache_results(..., checked_hashes=dmm_checked)` writes `"False"` only for hashes DMM answered for (RD and AD).
  - `_offer_unanswered_rd_torrents`: RD torrents that no service confirmed and DMM did not answer for
    go to `_store_unverified_rd_torrents` with `unverified=True` and a logged reason.
  - Scraper `debrid` markers ("RD"/"AD") are honoured.
  - `_split_by_db_cache` lower-cases hashes.
  - `store_torrent` lets a verified copy replace an unverified one.
  - Pre-emptive termination (`_prem_terminate`, types 0 and 2) counts only verified cached torrents
    (`statistics.filtered.torrentsCachedVerified`). Unverified torrents cannot end the scrape after the
    first provider batch while DMM is down. `torrentsCached` still counts them for the window and
    `_is_playable_source`.
- `modules/source_sorter.py` `_get_cache_confidence_key` is a new leading sort key:
  verified, cloud, hoster and direct (2) > unverified RD (1) > plain uncached torrent (0).
  Closes STATUS open item 2.
- `gui/windows/source_window.py` + strings.po #31129 ("Unverified"): the source window shows "REAL DEBRID (UNVERIFIED)".
- `modules/prism_version.py` `_clear_uncached_debrid_hashes` calls `DebridCache.clear_uncached_entries`
  (`database/debridCache`) on every version change.
- `common/source_utils.py` `get_filter_season_pack_fn`:
  - `f"s%{season_fill}"` could never match. It is replaced by `(?:s|season ?)0*N(?![a-z0-9])` with an optional year.
  - New guard: a video file is never treated as a season pack (title ending in mkv, mp4, avi, m4v,
    mov, wmv, webm, m2ts, ts, mpg, mpeg or flv).
  - Closes STATUS open item 3.

## (f) Verification
Live harness: the real repo `external_cache`, IMDb + Kitsu contexts, 43 Torrentio hashes, empty `rd.auth`.

| | 5.0.57 code | 5.0.58 code |
|---|---|---|
| `S01E01` releases confirmed cached | 0 / 17 | **10 / 17** (incl. the REPACK from the Seren log) |
| Cached hashes total | 7 | 26 |
| DMM | 403 on every call | answered for 43 / 43 |
| Repeat call within 60 s | n/a | 0 HTTP requests |

- Pre-fix probe, per service: DMM with a server-issued token 25/43 available; Torrentio `[RD+]`
  7 (IMDb) / 7 (Kitsu); AIOStreams 4 / 0; Comet 0.
- Offline harnesses: 29/29 worker checks (persistence, unverified offer, markers, AD, pre-emptive
  termination ignores unverified torrents), 59/59 season-pack cases, sorter order cached RD > hoster >
  unverified RD > uncached.
- Not verified: running in Kodi, the user's own RD token, the contents of the user's debridCache.

## (g) How to confirm in kodi.log (enable debug logging)
1. Install 5.0.58. The first start logs `Clearing uncached debrid hashes on Prism version change` and
   `DebridCache: Cleared N uncached entries`. *Tools -> Clear Local Torrent Cache* does the same manually.
2. Scrape Lord of Mysteries S01E01 and look for:
   - `ExternalCache: DMM RD returned N cached hashes (checked X of Y)`
   - `ExternalCache RD: N total cached hashes (DMM answered for X of Y)` with X > 0
   - **no** `ExternalCache: DMM RD check failed: 403 ...`
3. If DMM is down you will instead see:
   - `DMM RD check failed: DMM challenge failed: ...`
   - `RD cache check: DMM availability check unreachable (no answer), offering N torrents unverified (checked on play)`

   Those sources show "(Unverified)" and are sorted last.

## (h) Residual risks
1. **DMM is not ground truth.** DMM is itself a crowd DB keyed by IMDb id. A hash it reports as
   unavailable is stored `"False"` for 4 h even if RD actually has it.
2. **Kitsu-only items never reach DMM.** For an item with no IMDb id, unconfirmed torrents are offered as unverified.
3. **Unverified sources cost a cycle on play.** Playing one that turns out uncached costs one
   add-magnet/delete cycle before the next source.
4. **DMM may change again.** `/api/challenge` is rate-limited per IP, and DMM may change the scheme
   again. Either way, unconfirmed torrents become unverified rather than uncached, and the failure is logged.
5. **Third-party key in the source.** `_TIO_FALLBACK_PARAM` (external_cache.py HEAD:38) embeds a third-party
   RD API key as the Torrentio fallback. It is inherited from upstream and should be reviewed or removed.
6. **a4kScrapers `apikeys` (low value).** Passing them would make Torrentio return `[RD+]` directly,
   but that duplicates `torrentio_check_cache`.
7. **Purge drops correct negatives too.** The purge on version change removes every negative,
   including correct ones, so the first scrape after an update re-checks everything.
8. **Pre-existing, not the cause.** The torrentCache TV `get_torrents` SQL applies `expires > now`
   only to its `single` clause (`database/torrentCache/__init__.py` HEAD:58-67).
