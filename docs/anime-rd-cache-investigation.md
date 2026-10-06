# Prism (5.0.56): anime episodes show 0 cached / 0 cloud sources with Real-Debrid

> Archived copy of the 2026-10-06 investigation report. The fix described here was later
> committed as ce0d509 and released as plugin.video.prism 5.0.57 (f7abc86). "Nothing was
> committed" and the `scratchpad\...` files below refer to the investigation session and no
> longer exist. Open follow-ups are tracked in `.wolf/STATUS.md`.

Repo: this repository (master @ 321cc4c). All paths below are relative to
`plugin.video.prism/resources/lib/`. "HEAD:n" = line in the unmodified file, "now:n" = line
in the working tree after the fix. Nothing was committed or pushed. The full diff is in
`scratchpad\fix.diff`.

---

## (a) Traced flow for an anime episode

**GUI to playback entry**
- Anime menus (`gui/animeMenus.py`) list episodes through `modules/list_builder.py`. Episode
  items get `action="getSources"` (list_builder.py:216/260, `_common_menu_builder`
  list_builder.py:1064). Smart Play builds the same URL (`modules/smartPlay.py:329`, `:572`).
- `modules/router.py:169-235` (`action == "getSources"`) calls `tools.get_item_information`,
  then `helpers.SourcesHelper.get_sources` (`modules/helpers.py:97-113`, `@use_cache(1)`;
  empty results are not cached), then `Sources(item).get_sources()` (`modules/getSources.py:126`).

**Where anime metadata is built** (`common/tools.py:410-546`, episode branch `:465-538`)
- The episode row comes from the Simkl sync DB (`_load_episode_item_information`, tools.py:388-406).
- The parent show row is read with `SELECT info, imdb_id, tmdb_id, tvdb_id FROM shows`
  (tools.py:529-538). `attach_show_scraper_context` (`simkl/field_map.py:904-928`) then runs
  `inherit_show_fields` (field_map.py:845-901) and sets `item["_parent_show_info"]`.
- **IMDb sources.** IMDb comes only from Simkl ids: `_apply_external_ids`
  (field_map.py:436-470, `ids.imdb` → `info.imdb_id`) and the show row's `imdb_id` column.
  `inherit_show_fields` copies `tvshow.imdb_id` only when the show has one (field_map.py:888-890).
  `finalize_playback_info` fills `info.imdb_id` only from `tvshow.imdb_id` / `imdb_show_id`
  (field_map.py:1066-1071). There is no other IMDb lookup (no TMDb external-ids or
  MAL→IMDb mapping). If Simkl has no IMDb for the anime entry, which is common for Simkl/MAL
  anime entries, especially sequel cours, the item has no `imdb_id`.
- **Anime-only fields.**
  - `mal_id` / `mal_show_id` / `anidb_show_id` are copied to the episode (field_map.py:891-897).
  - `anilist_id` / `kitsu_id` stay on the show info (`_SIMKL_EXTRA_INFO_KEYS`, `meta/storage.py:94-106`).
  - Native Simkl numbering is kept in `anime_episode` / `anime_season` (field_map.py:828-836).
  - Menu `season` / `episode` are TVDB-based (`anime_menu_season` field_map.py:712-740).
- **Anime detection.** `simkl/anime_scraper_context.py:10-29` (`is_anime_item`: catalog anime,
  or mal/anidb/anilist/kitsu ids, or an anime genre). `catalog_profiles.resolve_catalog_from_item_information`
  sets `info.catalog` (tools.py:440-447).

**Scraping**
- `Sources._scrape_catalog` returns `"anime"` (getSources.py:471-486), so providers come from
  `providers.get_relevant(catalog="anime")` (:501-503).
- `_get_provider_sources` (getSources.py:556-625) builds `simple_info` with
  `_build_simple_show_info` (:981-1047). For anime it adds `build_anime_simple_info_fields`
  (mal/anilist/kitsu/tvdb ids, `simkl_episode_number`, alternative season/episode), and
  `absolute_number` becomes `simkl_episode_number` (:1022-1025). It then calls
  `provider.episode(simple_info, info)`.
- Torrent results are normalised (`_process_torrent_source` :627-640), added to `allTorrents`
  (shown as "torrents"), and passed to `TorrentCacheCheck.torrent_cache_check(...)` (:604-616).
  The local torrent DB path does the same (:412-421).

**Cache verification** (`TorrentCacheCheck`, getSources.py HEAD:1240-1518)
1. `_init_db_cache_rows` / `_split_by_db_cache`: hashes with any non-expired row in
   `database/debridCache` count as "known". Rows marked "True" are stored as cached; anything
   known is never rechecked (HEAD:1261-1285; `debridCache/__init__.py:82-90`).
2. A torrent with a provider `rd_cached` flag is accepted (no a4kScrapers provider sets it).
3. **Everything else needs `external_cache.check_rd_external(hash_list, imdb, season, episode)`,
   and that call is gated on `imdb`** (HEAD:1418-1420). The lookup is DMM + Torrentio + Comet +
   AIOStreams, all keyed on IMDb (`debrid/external_cache.py` HEAD:147-149, 229-232, 289-291,
   347-349, 416-427).
4. The fallback `RealDebrid.check_cache_batch` (`debrid/real_debrid.py:274-300`) calls
   `/torrents/instantAvailability`, which RD disabled in late 2024. It only runs when every
   external check fails outright (`success is False`). The external checks swallow their own
   errors and return empty sets, so that branch is practically unreachable, and it would
   return nothing anyway.
5. `_write_cache_results(unchecked, confirmed, "rd")` (HEAD:1287-1303, 1432) writes **every**
   unchecked hash as "True" or "False". "False" rows live 4 h (`debridCache/__init__.py:10-11, 68`).
- `store_torrent` (HEAD:1316-1347) fills `torrentCacheSources` and `cached_hashes`.
  `_finalise_results` (HEAD:323-349) returns sources only from those. Anything else is
  "uncached" and goes to cache assist (HEAD:334-339).

**Cloud sources**
- `_user_cloud_inspection` (getSources.py:766-814) runs `RealDebridCloudScraper.get_sources`
  (`modules/cloud_scrapers.py`) when `rd.cloudInspection` is enabled (default true).
- `list_torrents()` returns RD "My Torrents", only the first page (RD default `limit=100`, per
  the official API docs).
- Torrent-level filtering is `_is_valid_pack`, then `_identify_items` (cloud_scrapers.py
  HEAD:63-66, 165-179, 98-130), both using `source_utils.cloud_episode_item_matches`.
- Then `_source_to_file` calls `torrent_info` per torrent and matches files by basename
  (HEAD:233-241). Matching is purely title-based: **no IMDb involvement**.

**Playback** (for context)
- The RD torrent resolver (`modules/resolver/torrent_resolvers/real_debrid.py:44-63`) calls
  `RealDebrid.check_hash` (real_debrid.py:302-330): add magnet → select files → accept only
  `status == downloaded`, otherwise delete and move on to the next source.
- Pack episode files are chosen by `get_best_episode_match_cloud` (`base_resolver.py:117-129`).

**How anime differs from TV**
- Same code path, but anime items often lack `imdb_id`.
- They carry MAL/AniList/Kitsu ids and native episode numbers that the cache check never used.
- Release names follow fansub conventions ("[Group] Show - 05", batches "(01-12)") rather
  than SxxEyy.

---

## (b) Root cause: 0 cached sources

**Primary cause.** Real-Debrid cache verification needs an IMDb id, and anime often has none.

Evidence:
- `getSources.py` HEAD:1418-1431 has the gate `if imdb:` around the only verification step.
  `_external_imdb_context` (HEAD:1253-1259) reads IMDb only from `tvshow.imdb_id` / `imdb_id`.
- With no IMDb id, no torrent is checked, none is stored, and all are recorded uncached.
- Commit 58fdbcf ("Add external debrid cache & DB support") introduced this. Before it,
  `_realdebrid_worker` marked every torrent as RD-cached (`git show 58fdbcf^:…getSources.py`
  line 1300-1307), exactly as Seren still does (see d). Movies/TV work for the user because
  they have IMDb ids.
- The same gate exists in `_all_debrid_worker` (HEAD:1388-1394).

**Aggravating cause.** Hashes that were never checked are persisted as "uncached".
`_write_cache_results(unchecked, ...)` (HEAD:1432) writes all of them as "False" for 4 h.
`_split_by_db_cache` treats them as known (HEAD:1283-1285), so re-scrapes within 4 h skip them
even if an id becomes available.

**Secondary cause.** Even with an IMDb id, anime used only IMDb-keyed lookups. Torrentio and
Comet index anime by Kitsu id (manifest `idPrefixes` `["tt","kitsu"]`, checked live).
MAL/AniList/Kitsu ids were present on anime items but unused.

**Fallback is dead.** `check_cache_batch` uses `instantAvailability`, which RD removed. It is
reached only when `success is False`, which almost never happens.

**Reproduction** (harness, HEAD tree, anime episode without IMDb, 3 scraped hashes):
`external_calls=[]`, `cached=0`, DB writes `{a:False, b:False, c:False}`.

**Ruled out:**
- No anime-specific branch in getSources filters cached torrents.
- `_is_playable_source` uses unfiltered counts (HEAD:315-321), so `SourceSorter` filtering is
  not the cause.
- Provider processing is not failing: torrents reach `allTorrents`, which the user sees.

---

## (c) Root cause: 0 cloud sources

The cloud path does not use IMDb, so the user's hypothesis does not cover it. Two things combine:

1. **Usually nothing to find.**
   - The RD cloud scraper only lists torrents already in the RD account (first 100).
   - Prism's cache check never adds magnets.
   - `rd.autodelete` defaults to **true** (settings.xml:1558-1560), so the resolver deletes
     played torrents (real_debrid.py:324-325). Torrents played via Seren with defaults are gone too.
   - 0 cloud sources is expected unless the user added the anime to RD by other means
     (DMM, RD website, autodelete off).
2. **Anime naming did not match when the torrent was there** (`common/source_utils.py`):
   - `_release_matches_absolute_episode` (HEAD:563-580) checks `" 005 "`, `" 5 "`, `"e5"`,
     but not `" 05 "`. "[SubsPlease] Show - 05 (1080p).mkv" never matched episodes 1-9.
     The episode and season regexes are anchored on the show title (`^…`: episode regex HEAD:719,
     season regex HEAD:418 via `_get_regex_pattern`, used at HEAD:785), so a leading "[Group]"
     defeats them.
   - Anime batch torrents ("[Judas] Show (Season 1) [1080p]", "(01-28)") have no SxxEyy or
     episode number, so the torrent-level filter (`_is_valid_pack` / `_identify_items`) dropped
     them before their files were inspected.
   - Harness on HEAD: an RD account with the episode as a single torrent and inside a batch
     found **0** files. Every anime "- 05" name in the test set matched nothing (0/6).
   - The same gap broke the **resolver's** episode pick inside cached anime batches:
     `get_best_episode_match_cloud` returned `None` for episode 5 in a "(01-28)" pack on HEAD.

---

## (d) What Seren does differently

- **Cache check.** klass-723/plugin.video.seren 3.0.75 (`resources/lib/modules/getSources.py:1164`)
  and the bbviking line in Prism's `upstream/update` (same function, line 1164) mark *every*
  scraped torrent as RD-cached with no verification:
  `for i in torrent_list: i['debrid_provider'] = 'real_debrid'; self.store_torrent(i)`.
  Seren has no instantAvailability call and no external cache.
  - "Cached" is verified only at play time by `RealDebrid.check_hash` (seren `debrid/real_debrid.py:246`,
    identical to Prism's).
  - So Seren's "20-40 cached" are really "all scraped torrents", which explains the
    discrepancy. It needs no IMDb id because it never checks.
- **Cloud.** Seren's cloud matching is stricter: anchored episode/season/show regexes only, no
  loose anime matching. It would not match "[Group] Show - 05" either. Prism's loose matcher
  was already ahead; it only lacked the two-digit and batch handling.
- **Inherited typo.** Both projects have `season_fill_check = f"s%{season_fill}"` (Seren :512,
  Prism now:799), so TV season packs named "S01" fail the season regex. Not anime-specific;
  left unchanged (see g).

---

## (e) Changes made (4 files, working tree only; revised after the code review "SHIP WITH FIXES")

### `debrid/external_cache.py`
- `_stremio_stream_id()` (now:137) builds the Stremio stream id. IMDb inputs produce exactly
  the old strings (`series/tt…:S:E`, `movie/tt…`). New: `kitsu:<id>` produces
  `series/kitsu:<id>:<ep>`. Used by `torrentio_check_cache`, `aio_check_cache`,
  `comet_check_cache` in place of the inline path building.
- `check_rd_external(..., extra_contexts=None)` (now:462) and
  `check_ad_external(..., extra_contexts=None)` (now:509):
  - Futures are built per context by `_rd_check_futures` / `_ad_check_futures` (now:439, 495)
    and unioned in one `_run_parallel_checks` call, so latency is unchanged.
  - DMM is skipped for `kitsu:` contexts because DMM is IMDb-only.
  - With no usable context they return `(set(), False)`.
  - Without `extra_contexts` the futures and requests are identical to before.
- `resolve_kitsu_id(mal_id, anilist_id)` (now:574) uses the keyless Kitsu mappings API
  (`kitsu.app`, fallback `kitsu.io`). Review fixes #2 and #5:
  - One plain `requests.get` per host, with no retry adapter and a timeout of at most 3 s
    (`_KITSU_TIMEOUT`, now:116).
  - The whole call is bounded by `KITSU_LOOKUP_BUDGET = 5` s (now:118).
  - It stops at the first failure (no second id) and caches nothing on failure.
  - Positives are cached 168 h, "no mapping" 24 h (`_kitsu_cache_set`, now:565).
  - The earlier `@use_cache(168)` on the retrying session is gone.

### `modules/getSources.py`
- `_is_anime_episode()` (now:1273): mediatype episode plus `is_anime_item`. This is the guard
  for all new behaviour.
- `AnimeKitsuLookup` (now:1594, lock now:1591; review #2) holds `("kitsu:<id>", None, simkl_episode_number)`:
  - Created once per scrape under a lock (`for_scrape`) and shared by every provider check.
  - A `kitsu_id` already in the metadata is used without any network call.
  - A MAL/AniList mapping runs in a background thread. In no-thread mode it runs only when a
    no-IMDb check asks for it.
- `Sources._start_anime_kitsu_lookup()` (now:374, called at now:148 right after
  `_get_imdb_info`) starts it before the local-cache check and the provider threads.
- `_external_lookup()` (now:1282):
  - Non-anime: `extra_contexts = []`.
  - Anime: `get(wait=not imdb)`. With an IMDb id it never waits (Kitsu not ready or failed
    means IMDb-only, exactly as before).
  - Without IMDb it waits at most until the lookup deadline (budget + 1 s from scrape start).
- `_realdebrid_worker` (now:1442) and `_all_debrid_worker` (now:1409) check
  `if imdb or extra_contexts`.
- **RD only, anime episodes with no IMDb and no Kitsu id**: `_store_unverified_rd_torrents`
  (now:1486) offers Seren-style RD sources, verified by the resolver on play.
  - They are now tagged `torrent["unverified"] = True` (review #7). Sorting them last would
    need a one-line change in `modules/source_sorter.py` `_get_sort_key_tuple`; that is a 5th
    file, so it was not done.
  - They are excluded from the debridCache write.
- AllDebrid (review #6): an anime episode with no usable id no longer writes its hashes as
  "uncached" (`not_checked`, now:1422).

### `common/source_utils.py`
- `_anime_padded_episode_match()` (now:597; review #1, #8) handles anime-only `05` / `e05` /
  `ep05` / `05v2`:
  - **Skipped:** a number after a counter word (`season s part pt vol volume cour batch disc`,
    now:568), e.g. "Season 01", "Vol 05", "Part 05", "Cour 01", "Batch 01".
  - **Kept:** when that word is part of the title ("2nd Season - 05", "Final Season - 05").
  - **Range bounds ignored:** "01 12", "05 12".
  - **Title numbers are not range bounds** ("Mob Psycho 100 - 05", "Zom 100 - 05" via
    `_token_in_show_title`, now:589).
  - "- 05 [720p]" works.
- Used only via `_release_matches_absolute_episode(..., anime=True, show_titles=…)` from
  `cloud_loose_episode_match`. TV matching is unchanged.
- `get_best_episode_match_cloud` (resolver pack pick; review #1): for anime with several
  full-path matches it prefers files whose **basename** matches (now:~1156). Folder names like
  "Season 01", "Season 1" or "(01-28)" can no longer make every file match and the largest win.
- `cloud_episode_file_matches()` (now:509): episode-only file matcher, without the season-pack regex.
- `cloud_anime_pack_candidate()` (now:706; review #4) requires two things:
  - a batch marker (`_ANIME_BATCH_MARKER`, now:703: a range of 2-4 digit numbers, `batch`,
    `complete`, `sNN`, `season N`);
  - the show title or a **multi-word** alias of at least 4 characters. Single-word aliases
    like "Bleach" and one-letter titles like "K" are ignored.

### `modules/cloud_scrapers.py`
- New hook `CloudScraper._identify_packs()` (now:132, default `_identify_items`); `get_sources`
  calls it (now:66). This is a no-op for all providers.
- `RealDebridCloudScraper`:
  - `_is_anime_episode_scrape()` (now:237).
  - `_is_valid_pack` accepts anime batch candidates (now:240).
  - `_identify_packs` keeps the `_is_valid_pack` result for anime (now:249).
  - For anime, `_source_to_file` uses `_identify_anime_episode_files` (now:255; review #3):
    episode matchers only, no season regex, then the best match (largest), not `[0]` of
    `_identify_items`.
  - Non-anime and movies are unchanged.

---

## (f) Verification performed

1. **Compile.** `python -m py_compile` on all 4 changed files (bytecode written to the
   scratchpad): **OK**. The repo has no `__pycache__` left and `git status` shows only the 4
   modified files.
2. **`scratchpad\harness.py`.**
   - Stubs `xbmc*`, `unidecode` and `resources.lib.modules.globals.g`, then imports the real
     `getSources`, `cloud_scrapers`, `source_utils`, `external_cache`.
   - Runs the real `TorrentCacheCheck.torrent_cache_check` (inline thread pool) with a fake
     external checker and fake RD, and the real RD cloud scraper with a fake RD API.
   - The same scenarios ran against a pristine HEAD copy (`git archive` to `scratchpad\orig`).
     Results are in `orig.json` / `fixed.json`.

   | Scenario | HEAD | Fixed |
   |---|---|---|
   | Anime, no IMDb, MAL 52991 | no external call, 0 cached, all written "False" | call with `extra_contexts=[("kitsu:46474",None,"5")]`, 1/1 cached, correct True/False writes |
   | Anime, no IMDb, kitsu_id on show | 0 cached | Kitsu lookup without mapping call, cached |
   | Anime with IMDb + MAL | IMDb lookup only | IMDb + Kitsu in one call |
   | Anime with no ids at all | 0 cached, all "False" | 3/3 offered as RD (unverified), **no DB rows** |
   | TV with/without IMDb, movie with/without IMDb | — | **identical to HEAD** (extra_contexts always `[]`) |
   | Anime loose matching, 9 names | 0 matched (also the 6 that should) | 6 expected matches; 0 false positives on "- 15", "- 06", "(01-28)", "(05-12)", "(01-05)", "05 06 07" |
   | RD cloud, anime (batch + single torrent + unrelated) | 0 found | ep 05 from the batch and the single torrent; `torrent_info` only for the 2 candidates |
   | RD cloud, TV | B2 | **identical** |
   | Resolver pack pick in "(01-28)" batch | `None` | correct "- 05" / "- 01" file |

   **Re-run after the review fixes** (harness v2: real worker threads as in the `getSources`
   action, real eager `_start_anime_kitsu_lookup`; files `orig.json` / `fixed.json`).
   - All 4 files `py_compile` OK. `git status` shows only the 4 files, no `__pycache__`.
     `scratchpad\fix.diff` refreshed.
   - **Movies/TV:** cache check with and without IMDb, TV cloud and TV episode matching are
     **identical to HEAD**. The only difference is the new `extra_contexts=[]` keyword seen by
     the fake checker. `harness_ext.py`: all 12 IMDb request/dispatch outputs are
     **byte-identical** to HEAD.
   - **Anime cache check:** same results as before. The no-id case has 3 sources flagged
     `unverified` and no DB rows.
   - **#2 timing:**
     - IMDb present, Kitsu taking 3 s: check done in **0.0 s**, IMDb-only.
     - No IMDb, Kitsu 2 s: waited 2.0 s, then used Kitsu.
     - No IMDb, Kitsu over budget: returned after 2.0 s (budget 1 s in the test), unverified fallback.
     - 4 concurrent provider checks: **1** resolve.
     - Real `resolve_kitsu_id` with Kitsu unreachable: 2 attempts (1 per host, timeout 3,
       no retries), `None`, 0 cache entries.
   - **#5:** live TTLs are 168 h positive, 24 h negative.
   - **#6:** AllDebrid with an anime and no ids writes 0 rows. TV without IMDb still writes 3 (unchanged).
   - **#1 / #8:** 22 anime naming cases pass (HEAD: 0 matches).
     - match: "- 05v2", "- 05 [720p]", "Season 01 - 05", "2nd Season - 05", "Final Season - 05"
     - no match: "Season 05", "Vol 05", "Part 05", "Cour 05", "Batch 05"
     - "Mob Psycho 100 - 05" and "Zom 100 - 05" match; "Mob Psycho 100 (01-12)" and
       "Zom 100 - 06" don't.
   - **Resolver pick, ep 1:**
     - "Season 01" folder: "- 01" (HEAD: None).
     - "Season 1" folder: "- 01" (**HEAD played "- 07"**, a pre-existing bug).
   - **#3:** RD batch with files "Season 1 - 03/05/07", ep 5: "season 1 - 05" (HEAD: "- 03").
   - **#4:** 8 batch-candidate cases pass. "Bleach (001-366)" is rejected for TYBW; "Bleach
     Thousand-Year Blood War (01-13)" is accepted; "[K] …" is rejected for title "K"; a
     name with no marker is rejected.

3. **`scratchpad\harness_ext.py`** (no network) compares the requests built by `external_cache`:
   - For IMDb TV/movie inputs, Torrentio/AIOStreams/Comet/DMM URLs and params, and the checks
     dispatched by `check_rd_external` / `check_ad_external`, are **identical** between HEAD
     and the fixed tree.
   - Kitsu requests are `…/stream/series/kitsu:46474:5.json` (Torrentio, Comet) and
     `{type: series, id: kitsu:46474:5}` (AIOStreams). DMM is not called for Kitsu.
   - With no context, the result is `(set(), False)` with nothing dispatched.
4. **Live checks** (public, keyless):
   - Kitsu mappings: MAL 52991 and AniList 154587 resolve to Kitsu 46474 through the patched
     code; an unknown MAL id gives `None`.
   - Torrentio `stream/series/kitsu:46474:5.json` returns 70 streams with infoHashes, the same
     as `tt22248376:1:5`.
   - Comet and Torrentio manifests list stream `idPrefixes ["tt","kitsu"]`.
   - RD API docs confirm `GET /torrents` default `limit` is 100.

**Not verified:**
- Running in Kodi.
- Real RD-keyed responses: the `[RD+]` cached marker from Torrentio/Comet with the user's
  token, and AIOStreams accepting `kitsu:` ids.
- The real Simkl metadata of the user's show: whether `imdb_id` / `kitsu_id` are actually
  missing.
- a4kScrapers output for that episode.
- `DebridCache` DB reads/writes (stubbed in the harness; the logic around them was exercised).

---

## (g) Residual risks / what to test in Kodi (enable debug logging)

1. **Clear stale cache first.** Run *Tools → Clear Local Torrent Cache* (`action=clearTorrentCache`,
   which also clears debridCache) or wait 4 h. Old runs persisted the anime hashes as
   "uncached" and they will not be rechecked until those rows expire.
2. **What to look for in kodi.log when scraping the anime episode:**
   - `Anime cache check: Kitsu lookup ('kitsu:NNN', None, 'E') (metadata | mal=… anilist=…)`, or `… unavailable (…)`
   - `ExternalCache: Torrentio … returned N cached hashes`, `ExternalCache RD: N total cached hashes`
   - If `extra=[]` and imdb is None: `RD cache check: no IMDb/Kitsu id for anime episode, offering N torrents unverified`.
     Those sources behave like Seren's: some will fail on play and the resolver moves to the next.
   - `ExternalCache: Kitsu mapping lookup failed …` points to network/DNS issues with kitsu.app.
3. **External-service dependency.** Verification still depends on Torrentio, Comet, AIOStreams
   and DMM indexing the scraped hashes under that IMDb/Kitsu episode. Obscure releases may
   still show as uncached (same limitation as TV). If those services are blocked for the user,
   anime and TV both show 0, because the external checks swallow errors and Prism cannot tell
   "none cached" from "service down". This is pre-existing in `_run_parallel_checks`.
4. **Kitsu numbering.** Kitsu numbers episodes per entry, and the code uses the native Simkl
   `anime_episode`. For specials, or Simkl entries that span several Kitsu entries, the
   episode may not line up. A wrong lookup cannot create false "cached" results (a hash
   confirmed cached is cached regardless of episode), but it lowers recall.
5. **Unverified fallback** (RD, anime with no ids only). Sources show as cached without proof.
   Playing an uncached one costs one add-magnet/delete cycle before the next source.
   - They carry `unverified: True` but still sort like verified sources.
   - A one-line key in `source_sorter._get_sort_key_tuple` would put them last; it wasn't
     done here because only the 4 files were in scope.
   - With Kitsu unreachable, an anime episode **with** IMDb runs IMDb-only (as before). One
     without IMDb waits at most ~6 s from scrape start, then falls back to unverified.
6. **Cloud coverage:**
   - Only the newest 100 RD torrents are inspected (pre-existing; not anime-specific).
   - With `rd.autodelete` on (default), played torrents do not stay in the cloud, so 0 cloud
     sources is often correct.
   - Each RD anime batch candidate costs one `torrent_info` call.
   - The old unpadded needles (" 5 ", " 12 ") still match "Season 5" or range ends such as
     "(01-12)" in combined folder+file titles (pre-existing). The new basename tie-breaker
     covers the resolver pack pick. TorBox/Offcloud/Premiumize cloud titles include the
     folder name and can still match such numbers.
   - Anime batches without a marker ("[Group] Show [BD 1080p]") are no longer RD cloud
     candidates (review #4 trade-off).
7. **Pre-existing TV issue, not changed:** `get_filter_season_pack_fn` uses `f"s%{season_fill}"`
   (source_utils now:856, inherited from Seren), so "Show.S01.1080p" season packs never match
   at torrent level in the cloud scraper. The harness shows the TV season pack B1 missing on
   both HEAD and the fixed tree. Worth a separate fix if TV cloud packs matter.
8. **Anime movies** (mediatype movie, catalog anime) are intentionally not changed and still
   need an IMDb id for the external check.
9. **Latent crash risks** seen but not touched (not the user's symptom):
   - `_torrent_filesize` divides by `info['show_episode_count']` / `episode_count`. A KeyError,
     None or 0 there would drop a whole provider's results.
   - `get_filter_show_pack_fn` calls `int(no_seasons)`. For TMDb-Helper synthesized episodes
     with `season_count=None` this raises and kills cloud inspection. Both are relevant only
     for external-play items.
