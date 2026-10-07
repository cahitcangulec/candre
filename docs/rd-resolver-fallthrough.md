# Prism 5.0.58: uncached Real-Debrid sources stop playback instead of falling through

> Investigation and fix of 2026-10-07, released as plugin.video.prism 5.0.59 (committed on master, not
> pushed yet). Follow-up to `docs/rd-cache-dmm-fix.md` (5.0.58).
> Paths are relative to `plugin.video.prism/resources/lib/`. "HEAD:n" is a line in 17664ae (5.0.58);
> other line numbers are the 5.0.59 tree. `SEREN/` is `plugin.video.seren/resources/lib/` of the Seren
> 3.0.62 install the user compares against. Open items are tracked in `.wolf/STATUS.md`.

## (a) Problem (user report)
- With 5.0.58, Real-Debrid (RD) torrents are listed as "Unverified" and only about half of them play
  ("50/50"). Seren 3.0.62 with the same a4kScrapers plays almost every source the user clicks.
- The 5.0.58 DMM fix works: from this machine DMM answers for 100 % of the hashes and reports 43-72 %
  of the scraped releases as cached, which matches the user's "50/50". The list alone does not explain
  the report. What differs is what happens when the user clicks a source that is not cached.

## (b) What Seren 3.0.62 really does
Seren checks nothing when it builds the list. It finds out on click and falls through silently.
- **No scrape-time check.** `_realdebrid_worker` labels every scraped torrent `real_debrid` without any
  API call (`SEREN/modules/getSources.py:1164-1171`). Torrentio is queried without a key: Seren never
  passes `apikeys` (`SEREN/modules/getSources.py:548, 553-559`), so there is no `[RD+]` marker, and
  Seren does not read the `debrid` field anyway.
- **A click hands over the rest of the list.** With `general.autotrynext` on (the default), the clicked
  source and every source below it go to the resolver (`SEREN/gui/windows/source_select.py:71-84`),
  which loops until one resolves (`SEREN/gui/windows/resolver_window.py:33-53`; silent path
  `SEREN/modules/resolver/__init__.py:42-62`).
- **The only real cache test is per source, at play time.** `check_hash` adds the magnet, selects the
  files, reads `torrents/info` once and accepts only `status == "downloaded"`; otherwise it deletes the
  torrent (`SEREN/debrid/real_debrid.py:246-274`).
- **An uncached torrent is an exception, so there is no prompt.** `check_hash(...)[hash]` raises
  `KeyError` on `{}` (`SEREN/modules/resolver/torrent_resolvers/real_debrid.py:34-37`). That becomes
  `ResolverFailure` (`SEREN/modules/resolver/__init__.py:197-210`), which is caught before the
  "manually select the file?" prompt (string 30490) is reached (`SEREN/modules/resolver/__init__.py:80-111`).
  The prompt only appears for a cached torrent whose file could not be matched
  (`SEREN/modules/resolver/torrent_resolvers/base_resolver.py:83-86, 102-113`).
- **Evidence.** In the user's Seren kodi.log, one click walked through 22 sources in 10.4 s with no dialog
  per failure (an anime that RD refused with `451 infringing_file`). The resolver window renders only
  after the loop, so the user never sees that a different, near-identical release played.
- Seren also refreshes the RD token and retries on any non-2xx response
  (`SEREN/debrid/real_debrid.py:203-206, 219-223`), which doubles every failed call.

## (c) What Prism 5.0.58 did wrong
- **Uncached returned an empty file list instead of raising.** `_fetch_source_files` returned `[]` when
  `check_hash` gave `{}` (`modules/resolver/torrent_resolvers/real_debrid.py` HEAD:45-48). That
  became "no file matched" (`FileIdentification`, or `_finalize_resolving(None)`), and
  `_resolve_debrid_source` returned `None` (`modules/resolver/__init__.py` HEAD:275-281; generic
  exceptions were swallowed too).
- **So every uncached source showed the manual-selection prompt.** `resolve_single_source` asked 30490
  (HEAD:119). The resolver window called it for every source with the default
  `allow_manual_prompt=True` (`gui/windows/resolver_window.py` HEAD:76), so the prompt came back after
  each uncached source.
- **"Yes" stopped the loop.** Yes re-probed the same uncached hash with pack select, found no files and
  raised `NoFileSelectionAvailable`. The window then set `user_cancelled` and broke out
  (`gui/windows/resolver_window.py` HEAD:81-83; hidden path `modules/resolver/__init__.py` HEAD:81-82).
  The next source was never tried, which the user sees as "not playable".
- **Where the raise went.** Upstream Prism `3fbb730` (2025-01-08, changelog 3.0.65 "Removed unnecessary
  error when RD magnet doesn't resolve", taken from bbviking `d444784`, 2024-12-05) removed the raise
  that made Seren 3.0.62 skip silently. Our fork's `.get()` in `_fetch_source_files` had the same effect.
- **Smaller defects in the same path.** The resolver harness reproduces all of them on HEAD (11/32 checks):
  - `check_hash` called `selectFiles` even when RD had never seen the hash (`magnet_conversion`), which
    starts a download (`debrid/real_debrid.py` HEAD:310).
  - With `rd.autodelete` on, a cached torrent was deleted before its link was unrestricted (HEAD:324).
  - With `rd.autodelete` off, a failed episode sent `DELETE torrents/delete/None`
    (`modules/resolver/torrent_resolvers/real_debrid.py` HEAD:73-75).
  - Any non-2xx response forced an OAuth refresh and a retry (`debrid/real_debrid.py` HEAD:213, 230,
    247), including 429/451/503/509.
  - Nothing capped the number of sources one click tries.
- **Scrape side (5.0.58).**
  - DMM "not available" was stored as "False" for 4 h and the hash was hidden
    (`modules/getSources.py` HEAD:1517), although DMM is a crowd DB, not an RD answer.
  - The dead `instantAvailability` call (`check_cache_batch`, RD error 37) was still a fallback
    (HEAD:1507).
  - A third-party RD key was used for Torrentio when the user had none (`debrid/external_cache.py`
    HEAD:48, inherited from upstream).
  - A url-only provider result raised `KeyError` in `_process_torrent_source` (HEAD:652) and lost the
    provider's whole batch.

## (d) What 5.0.59 changes
### Resolver: click-time fall-through (Seren behaviour)
- `modules/exceptions.py:141` `TorrentNotCached(ResolverFailure)` carries `info_hash`, `reason` and
  `persist`. It logs no error stacktrace when created. `persist=True` only for an authoritative
  "not cached" answer.
- `debrid/real_debrid.py:270` `check_hash(hash, keep_torrent=False)`:
  1. `addMagnet`. A refused or failed add raises `TorrentNotCached(persist=False)`. 429/451/503/509 are
     logged as warnings with their meaning (`RD_PROBE_LIMIT_ERRORS`, `:32`).
  2. `torrents/info`. `magnet_conversion` or an error status (`magnet_error`, `error`, `virus`, `dead`)
     deletes the torrent **without** `selectFiles` and raises `TorrentNotCached`.
  3. `torrent_select_all` reuses that info (`:363`). A non-2xx `selectFiles` (for example 509, slots
     full) deletes the torrent and raises `persist=False`.
  4. `torrents/info` again, with one 1.5 s re-check while the status is `waiting_files_selection`,
     `queued` or `magnet_conversion` (`RD_PROBE_RECHECK_STATUSES`, `:28`).
  5. Only `downloaded` is accepted. Any other status deletes the torrent and raises `persist=True`.
  6. `keep_torrent=True` (the resolver) keeps a cached torrent until its link is unrestricted.
     `modules/download_manager.py:784` keeps the old contract (default `keep_torrent=False`).
- `debrid/real_debrid.py:228, 245, 262` refresh the token and retry only on HTTP 401.
  `:412` `delete_torrent` ignores an empty id. The dead `check_cache_batch` and `_get_url_no_refresh`
  (`instantAvailability`) were removed.
- `modules/resolver/torrent_resolvers/real_debrid.py`:
  - `:54` `_fetch_source_files` re-raises `TorrentNotCached`. `:92` `_store_probe_result` writes RD's
    answer into the debrid cache under the key `"rd"` that the scrape reads: `"True"` (24 h) on
    `downloaded`, `"False"` (4 h) when `persist` is set.
  - `:45` `resolve_magnet` deletes the kept torrent when resolving fails. `:104` `_delete_torrent`
    deletes only a real id and drops the cached file list, so a manual retry probes again. `:116`
    `_do_post_processing` deletes after the unrestrict: always on failure, on success only with
    `rd.autodelete`.
- `modules/resolver/__init__.py`:
  - `:33` `MAX_RESOLVE_ATTEMPTS = 10` sources per click or auto-play. The window uses the same cap
    (`gui/windows/resolver_window.py:64`) and shows `n/10`.
  - `:144-145` `except TorrentNotCached` (before `except ResolverFailure`) logs one debug line and returns
    `(None, None)`, so the loop moves on silently.
  - `:120` the 30490 prompt is shown at most once per play attempt (`self.manual_prompt_shown`), and only
    when the torrent was cached but no file matched. "Yes" with nothing to pick moves on to the next source.
  - `:278-300` `_resolve_debrid_source` re-raises `ResolverFailure`, `TorrentNotCached` included. Only
    `FileIdentification` returns `None`, which allows the prompt. Any other error becomes
    `ResolverFailure`: the source is skipped without the prompt, as in Seren.
  - `:85` and `gui/windows/resolver_window.py:92` log `Resolver: none of the N tried sources could be
    resolved`.

### Scrape: cache hints only promote
- `modules/getSources.py:1610` `_realdebrid_worker`:
  - debridCache rows come first. `"True"` is verified (`local`). A live `"False"` row (written by the
    resolver) hides the hash, which is counted as `dropped` (`:1621`).
  - Scraper markers (`debrid == "RD"`, `rd_cached`) are verified (`torrentio`).
  - Answers from `external_cache.check_rd_external` only promote. Every other hash is offered unverified
    with a reason (`_offer_unconfirmed_rd_torrents`, `:1662`).
  - Only `"True"` is persisted (`:1656`, `checked_hashes=()`). The `check_cache_batch` fallback is gone.
- `modules/getSources.py:1334` `RdCacheSummary` (thread-safe) aggregates every provider batch. `:339`
  `_finalise_results` logs it once per scrape at info level.
- `modules/getSources.py:581-610` `_provider_apikeys` and `_call_provider`: `apikeys={'rd': rd.auth}`
  goes to torrent providers only when `rd.scraperCachedOnly` is on (default off). Providers that do not
  take the keyword are called again without it (`TypeError` fallback).
- `modules/getSources.py:708` `_torrent_source_hash` takes the hash from `hash`, the magnet or a Torrentio
  resolve URL, builds a magnet when there is none and drops the key-bearing URL. `:424` the two-week
  local torrent cache stores torrents without scraper cache markers.
- `debrid/external_cache.py`:
  - `:259` there is no fallback key any more.
  - `:607-624` Torrentio, Comet and AIOStreams run only with the user's `rd.auth`. DMM always runs.
  - `:342` DMM requests send the `Referer` and `Origin` its web client sends.
  - `:558` `by_checker` collects per-service counts for the summary.
- `common/tools.py:682-705` the legacy provider logger (used by a4kScrapers) redacts debrid keys in URLs.
- `resources/settings.xml:1568` new setting `rd.scraperCachedOnly` (strings #31140 and #31141).
- `addon.xml` 5.0.59: the version change purges stale `"False"` rows
  (`modules/prism_version.py:28` `_clear_uncached_debrid_hashes`).

## (e) Verification (Kodi cannot run here)
- `python -m py_compile` and a Python 3.8 grammar parse pass for every changed file. `settings.xml`
  parses, and strings #31140/#31141 are unique.
- Resolver harness: **32/32**. It runs the real resolver, the RD torrent resolver, the `RealDebrid` HTTP
  layer, the resolver window loop and a real SQLite debridCache against a fake RD server. The same harness
  on HEAD gives 11/32: a prompt per uncached source, `delete/None`, delete before unrestrict, no cap,
  refresh on 429/451/503/509 and no cache rows.
- Scrape harness: **39/39**. It runs the real `getSources`, `external_cache` and `common.tools` against fake
  HTTP.
- Integration: **5/5**. The real resolver writes the real debridCache, and the real RD worker reads those
  rows through the real `DebridCache` code.
  - A `"False"` row is hidden and counted `dropped=1`.
  - A `"True"` row is verified as `local=1`.
  - A 429 (not persisted) and an unprobed hash are offered unverified.
  - DMM is asked only for the hashes without a row.
- Live run (2026-10-07; DMM and Torrentio were read only, and no RD torrent call was made): see the table
  in (g).

## (f) What the user should see in Kodi
- After the update, kodi.log shows `Clearing uncached debrid hashes on Prism version change` and
  `DebridCache: Cleared N uncached entries`.
- Each scrape logs one info line. Debug logging is not needed for it:
  `RD cache summary: verified=N (torrentio=N dmm=N comet=N aio=N local=N) unverified=N dropped=N dmm_answered=X/Y reason=...`
  - `verified`: confirmed by a service or by an earlier play. These are listed first.
  - `unverified`: nobody confirmed them. They are listed after the verified ones as
    "REAL DEBRID (UNVERIFIED)" and checked on play. The list is longer than in 5.0.58 because DMM
    negatives are no longer hidden.
  - `dropped`: RD itself said "not cached" on a play in the last 4 h.
  - `reason=` names why hashes stayed unverified, for example
    `DMM availability check unreachable (no answer)`,
    `no IMDb id for the DMM availability check (Kitsu-only lookup)`,
    `not listed as cached by DMM/Torrentio/Comet/AIOStreams` and
    `no rd.auth: Torrentio/Comet/AIOStreams RD checks skipped`.
- Clicking a source that is not cached shows no dialog. With "Auto try next link on resolve failure"
  (`general.autotrynext`, on by default), Prism silently tries the next source, up to 10 per click, and
  the resolver window shows `n/10`. With that setting off, only the clicked source is tried.
  - With debug logging on, each skipped source logs
    `Skipping source, not playable on real_debrid now: <hash>: status <status>`.
  - RD limits show as warnings, for example
    `RD probe addMagnet for <hash>: HTTP 451 (infringing file or add pause), skipping source`.
- "Failed to resolve a playable file, would you like to manually try select the file?" appears only when a
  torrent is cached but no file matched, at most once per click. "No" continues with the next source.
- If none of the tried sources plays, kodi.log shows `Resolver: none of the N tried sources could be
  resolved` (info) and Kodi shows the notification "No playable sources found for item".
- With Auto Delete on, no probe torrent is left in the RD account.

## (g) Decision log
- **One exception class for the silent skip.** Uncached and limited sources take the same silent skip;
  `persist` only decides whether RD's answer is stored. The other debrid resolvers do not raise it yet.
- **Only RD's own answer may hide a hash.** The resolver stores RD's probe result (`"True"` for 24 h,
  `"False"` for 4 h). DMM, Torrentio, Comet and AIOStreams are crowd caches: a hash missing there proves
  nothing, so they only promote. This is the POV model; Umbrella reverted hiding DMM negatives in 6.7.69.
- **451 is not persisted** (nor are 429, 503, 509 or request errors). DMM's measurements show that RD also
  answers `451 infringing_file` while it pauses adds on an account. A 451 therefore says nothing reliable
  about the hash, and a 4 h negative could hide good sources. The cost is one `addMagnet` per click on a
  hash that really is blocked.
- **Token refresh only on 401.** RD answers 401 for a bad token. A refresh after a 429 or 451 only doubles
  the request count.
- **No scrape-time RD probing.** The reasons are RD's limits:
  - RD documents 250 requests per minute, and refused requests count toward it.
  - DMM measured about 30 `addMagnet` per minute per account before a 429.
  - DMM also measured account-wide add pauses (`451`, 21 s to about 5 min) after only 2-9 adds of hashes
    new to the account. A fast season sweep reported 13 of 15 cached torrents as uncached.
  - Probing a list of 20-70 torrents at scrape time would spend the add budget the user's next click
    needs, and could make that click fail.
  - No maintained addon probes at scrape time: not POV, Umbrella, Fen Light, Seren, Otaku or upstream
    Prism.
- **Cap of 10 sources per click.** An uncached source costs 3-6 RD calls, so one click stays around 60
  calls. There is no setting for the cap yet.
- **a4kScrapers `apikeys` is opt-in (`rd.scraperCachedOnly`, default off).** With the key, a4k's Torrentio
  returns only Torrentio's `[RD+]` streams. The live run used the real a4k Torrentio and the real worker
  against live DMM and Torrentio, with Comet and AIOStreams stubbed:

  | Title | Setting off, rd.auth set | Setting on | No rd.auth (DMM only) |
  |---|---|---|---|
  | Inception | 68 (57 verified + 11 unverified) | 66 (66 verified) | 68 (53 + 15) |
  | Breaking Bad S01E01 | 36 (24 + 12) | 34 (34 + 0) | 36 (15 + 21) |
  | Lord of Mysteries S01E01 | 23 (9 + 14) | **0** | 23 (9 + 14) |

  - Mainstream titles gain an all-verified list. Anime and new episodes can lose every Torrentio result:
    Torrentio's `[RD+]` list for them is small and pack-heavy, and a4k's episode filter drops the packs.
  - Without the setting, `torrentio_check_cache` already sends the user's key. It confirmed 47 of
    Inception's 68 releases.
  - Keyed streams carry no hash, only a resolve URL that contains the user's key. The hash is therefore
    parsed from the URL, the URL is dropped, and a4k's `GET:` log line is redacted.
- **Third-party Torrentio key removed.** The Torrentio, Comet and AIOStreams RD checks need the user's own
  `rd.auth`. Without it, only DMM runs.
- **Unrestrict before delete.** The resolver keeps a cached torrent until its link is unrestricted and
  deletes it afterwards. Whether RD links still work after their torrent is deleted is unverified.

## (h) Open items
1. Confirm 5.0.59 in Kodi with the log lines in (f).
2. The AllDebrid worker still stores DMM negatives as "False" and hides them
   (`modules/getSources.py:1575` `_all_debrid_worker`, `:1606`). The AllDebrid, Premiumize, TorBox and
   Offcloud resolvers do not raise `TorrentNotCached`, so their uncached torrents can still show the
   manual-selection prompt, once per click.
3. Optional: a top-N scrape-time RD probe of unverified sources, off by default, if list accuracy matters
   more than the add budget. It would need at most a few adds, at least 3 s apart, and a stop at the first
   429, 451 or 509.
4. a4kScrapers Torrentio has no Kitsu support. Anime without an IMDb id gets no Torrentio results, with or
   without `rd.scraperCachedOnly`.
5. Minor:
   - There is no setting for the 10-source cap.
   - There is no process-wide RD rate limiter.
   - `modules/download_manager.py` still unrestricts after its probe has deleted the torrent (Auto Delete on).
