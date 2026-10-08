# STATUS — candre

> Single source of truth for resuming work. Read this FIRST when starting a session.
> Update this file at the end of every work phase so the next `/clear` resumes in 1 read.
> Last updated: 2026-10-08 (5.0.59 published to gh-pages 53be482; repository.candre 1.0.1 committed on master, not pushed: checksum verify)

---

## ✅ Done

- **2026-10-08 — 5.0.59 published; Kodi still showed 5.0.58; repository.candre 1.0.1 committed on master, not pushed.**
  - Timeline (UTC): master pushed `7dfb7c1` (5.0.59) at 19:21:53; CI run 37831410319 published gh-pages
    `53be482` at 19:22:15. GitHub's automatic Pages build errored (superseded duplicate, "Page build failed.",
    0 s); the build the workflow requested built the tip at 19:22:55. Served `addons.xml` (md5
    `e624466f1306c2bd78a8ae7604c5c429`) lists 5.0.59 since 19:22:50. The zip is valid; its requires are
    unchanged vs 5.0.58.
  - The 5.0.58 zip is no longer on gh-pages (HTTP 404), so there is no rollback to 5.0.58 from Kodi.
  - Kodi still showed 5.0.58 at ~19:31 UTC. Likely cause (not confirmed on the device): a refresh inside the CDN `max-age=600` window can fetch the
    new `addons.xml.md5` with a cached old `addons.xml`. `repository.candre` 1.0.0 had no `checksum verify`,
    so Kodi stored that pair and kept 5.0.58 until the md5 changes again or the repository add-on is
    reinstalled. Prism's Provider Tools > Check For Updates checks provider packages only
    (`install_manager.check_for_updates`), never `plugin.video.prism`, so its "no updates" message is
    unrelated to the Kodi repository.
  - Fix (committed on master, not pushed): repository.candre 1.0.1 with `<checksum verify="md5">` (a mismatch
    now fails and retries; the md5 URL is unchanged). `publish-repo.yml`'s Pages step waits for the automatic
    Pages build (see Release flow). Kodi refresh facts rewritten in "Kodi update rule". Bug log: bug-012.
- **2026-10-07 — plugin.video.prism 5.0.59: uncached RD sources fall through silently (pushed 2026-10-08; published as gh-pages `53be482`).**
  User report after 5.0.58: RD torrents listed "Unverified" and only about half play ("50/50"), while
  Seren 3.0.62 plays almost every click. Write-up: `docs/rd-resolver-fallthrough.md`.
  - Root cause: `_fetch_source_files` returned `[]` for an uncached torrent (upstream `3fbb730` removed
    Seren's raise), so every uncached source showed the "manually select the file?" prompt (30490) and
    "Yes" stopped the loop. Seren skips uncached sources silently and tries the next one.
  - Resolver: `TorrentNotCached` (`modules/exceptions.py`) from a hardened `RealDebrid.check_hash`
    (no `selectFiles` on `magnet_conversion`, one 1.5 s re-check, only `downloaded` accepted,
    `keep_torrent` so the link is unrestricted before the delete) is skipped silently; prompt only for
    cached-no-match, once per play; max 10 sources per click; token refresh only on 401;
    `delete_torrent` ignores an empty id. RD's answer is stored in debridCache under `"rd"`
    ("True" 24 h, "False" 4 h; 429/451/503/509 never stored).
  - Scrape: DMM/Torrentio/Comet/AIOStreams answers only promote (only "True" persisted for RD); one
    `RD cache summary` info line per scrape; third-party Torrentio key removed (Torrentio/Comet/AIOStreams
    need the user's `rd.auth`); `instantAvailability` fallback and `check_cache_batch` deleted; DMM
    `Referer`/`Origin`; url-only provider results no longer lose the batch; opt-in `rd.scraperCachedOnly`
    (default off) passes `apikeys` to a4kScrapers; `common/tools.py` redacts debrid keys in provider logs.
  - Verification: resolver harness 32/32 (HEAD 11/32), scrape harness 39/39, resolver-to-scrape
    integration 5/5, py_compile + Python 3.8 grammar for every changed file. Harnesses live in the
    session scratchpad (not in the repo).
- **2026-10-07 — plugin.video.prism 5.0.58 is live (deployed 2026-10-06 23:59 UTC).**
  - A manual Pages build request (`gh api -X POST repos/cahitcangulec/candre/pages/builds`,
    2026-10-06 23:58:47 UTC, HTTP 201) built gh-pages 3cc2944 in 23 s.
  - https://cahitcangulec.github.io/candre/ serves addons.xml with plugin.video.prism 5.0.58
    (addons.xml.md5 `1aef23e379d972cb215dc53b7eef877c`) and
    `zips/plugin.video.prism/plugin.video.prism-5.0.58.zip` (HTTP 200, 8596527 bytes). No CDN lag.
- **2026-10-07 — Automatic publishing (pushed; origin/master at 17664ae).**
  - `.github/workflows/publish-repo.yml` ("Publish Kodi repository") runs on every push to master
    that touches `plugin.video.prism/`, `context.prism/`, `repository.candre/`,
    `tools/build_repo.py` or the workflow, and on manual dispatch. It rebuilds gh-pages with
    `tools/build_repo.py` and pushes it as github-actions[bot] only if the tree changed.
  - `tools/build_repo.py --reuse-zips <dir>` keeps an already-published `<addon>-<version>.zip`
    byte for byte (and takes addon.xml/art from it), so runs without a version bump change nothing.
    Zip timestamps are now the ref's commit time (UTC) instead of the local build time.
  - History: the push of gh-pages 3cc2944 (2026-10-06 21:45 UTC) never started a Pages build (likely
    a GitHub incident, unconfirmed), so the workflow's last step requests a Pages build whenever the
    deployed commit is not the gh-pages tip. 3cc2944 itself was deployed by hand (entry above).
- **2026-10-06 — RD cache detection restored (49a0a40, released as plugin.video.prism 5.0.58 in 3db18dc, gh-pages 3cc2944).**
  User report: in 5.0.57, every RD torrent for "Lord of Mysteries" S01E01 showed as uncached,
  while Seren 3.0.62 showed many as cached.
  - Seren's "cached" is unverified labelling: its `_realdebrid_worker` marks every scraped
    torrent `real_debrid`, and Seren's own kodi.log shows "Failed to resolve source" on play.
  - Root cause 1: the DMM availability check had returned 403 on every call since DMM moved to
    server-issued challenge tokens on 2026-08-31. This degraded cache detection for all titles.
  - Root cause 2: failed or unanswered checks were persisted as uncached for 4 h.
  - Fixes in `debrid/external_cache.py`:
    - `_dmm_get_challenge`; DMM hashes sent in chunks of 100.
    - Checkers return `None` when they got no answer.
    - Comet skips bases that return only error streams; expired `rd.auth` is refreshed.
    - Dead vortetos AIOStreams URL removed; 60 s memo; URLs redacted in logs.
  - Fixes in `modules/getSources.py`:
    - "False" is written only for hashes DMM answered for.
    - Unanswered RD torrents are offered `unverified=True`.
    - Scraper `debrid` RD/AD markers are honoured.
    - Pre-emptive termination counts verified cached torrents only (`torrentsCachedVerified`), so
      unverified torrents cannot stop the scrape early while DMM is down.
  - Unverified sources sort last (`source_sorter._get_cache_confidence_key`) and are labelled
    "REAL DEBRID (UNVERIFIED)" (string #31129).
  - Stale negatives are purged on version change (`prism_version` →
    `DebridCache.clear_uncached_entries`).
  - Season-pack "S01" regex fixed (`common/source_utils.get_filter_season_pack_fn`).
  - Closes former open items 2 (unverified not sorted last) and 3 (S01 season packs).
  - Live A/B: S01E01 releases confirmed went from 0/17 to 10/17. Write-up: `docs/rd-cache-dmm-fix.md`.
- **2026-10-06 — Anime Real-Debrid fix (ce0d509, released as plugin.video.prism 5.0.57 in f7abc86).**
  Anime episodes showed 0 cached / 0 cloud RD sources.
  - `modules/getSources.py`: the RD cache check was gated on an IMDb id, which anime often lacks.
  - `debrid/external_cache.py`: Kitsu-id lookups (MAL/AniList -> Kitsu) for Torrentio/Comet/AIOStreams.
  - Seren-style unverified RD fallback for anime with no ids.
  - `common/source_utils.py`: anime zero-padded episode matcher.
  - `modules/cloud_scrapers.py`: anime batch handling.
  - **This did NOT fix the user's case.** Lord of Mysteries has both IMDb and Kitsu ids; the real
    cause was DMM auth (entry above). Write-up: `docs/anime-rd-cache-investigation.md`.
- **2026-10-06 — Kodi repository published.** `repository.candre` 1.0.0 (37aca8d); gh-pages
  serves addons.xml + zips at https://cahitcangulec.github.io/candre/ (gh-pages f2630d4).
- **2026-10-06 — Project brain.** OpenWolf 2.0.1 set up (Claude Code + Codex hooks), build
  script committed as `tools/build_repo.py`, investigation report as `docs/`.

---

## 🚀 Next phase

**Project:** candre = fork of Kodi addon Prism (upstream Goldenfreddy0703/Prism, a Seren fork),
https://github.com/cahitcangulec/candre.
- Branches: `master` = code, `gh-pages` = published Kodi repo (https://cahitcangulec.github.io/candre/).
- Addons: `plugin.video.prism/` 5.0.59 (published), `context.prism/` 4.0.2, `repository.candre/` 1.0.1
  (committed on master, not pushed; 1.0.0 is published). Python 3.

**Goal:** (1) the user pushes master (`git push origin master`): CI publishes repository.candre 1.0.1
(checksum verify) and runs the new Pages wait (see Release flow). Check that the run is green, wait 10 min,
then "Check for updates" in Kodi. (2) The user confirms 5.0.59 in Kodi (open item 1). Then decide on the
remaining open items.

### Open items (code paths relative to `plugin.video.prism/resources/lib/`)
1. **Confirm 5.0.59 in Kodi.** 5.0.58 was never confirmed on the device; 5.0.59 supersedes it.
   - Published: gh-pages `53be482` (CI run 37831410319), served since 19:22:50 UTC on 2026-10-08. At ~19:31 UTC
     Kodi still showed 5.0.58 (see Done, 2026-10-08).
   - To do in Kodi: (a) Add-ons screen header button "Check for updates", at least 10 min after the latest
     publish (the 19:22 UTC window closed at 19:32 UTC); (b) Prism info page > Versions: install the entry
     "5.0.59 / Candre Repository" (keeps settings). If that entry is still missing after a check, the client
     is stuck: see "Stuck client, fallback only" under "Kodi update rule".
   - Kodi only auto-updates Prism if its origin is "Candre Repository" (see "Kodi update rule").
   - After the update: `Clearing uncached debrid hashes on Prism version change` and
     `DebridCache: Cleared N uncached entries`.
   - Each scrape (info level): `RD cache summary: verified=N (torrentio=N dmm=N comet=N aio=N local=N)
     unverified=N dropped=N dmm_answered=X/Y reason=...`. Expect `dmm_answered` X = Y and no
     `DMM RD check failed: 403`; `dropped` counts hashes RD itself rejected on a play in the last 4 h.
   - Click an unverified source that is not cached: no dialog, the next source plays (with "Auto try
     next link", default on), at most 10 tried. Debug log per skipped source:
     `Skipping source, not playable on real_debrid now: <hash>: status ...`; RD limits as warnings
     `RD probe addMagnet for <hash>: HTTP 451 (infringing file or add pause), skipping source`.
   - Prompt 30490 only for a cached torrent without a matching file, once per click.
   - All tried sources failed: `Resolver: none of the N tried sources could be resolved` and the
     notification "No playable sources found for item".
2. **AllDebrid still hides DMM negatives.** `modules/getSources.py` `_all_debrid_worker` stores "False"
   for hashes DMM answered "not available" (`checked_hashes=dmm_checked`) and has no unverified tier.
   The AllDebrid/Premiumize/TorBox/Offcloud resolvers do not raise `TorrentNotCached`, so their uncached
   torrents can still show the manual-selection prompt (once per click).
3. **Optional top-N scrape-time RD probe** (off by default) if the user still wants list accuracy:
   probe a few unverified sources after the list is shown, at least 3 s between adds, stop at the first
   429/451/509. Caveat: RD allows 250 requests/min (refused ones count) and DMM measured about 30
   adds/min per account and account-wide 451 add pauses (21 s to about 5 min) after only 2-9 new-hash
   adds, so probing spends the budget the user's click needs. No maintained addon probes at scrape time.
4. **a4kScrapers Torrentio has no Kitsu support.** Anime without an IMDb id gets no Torrentio results,
   with or without `rd.scraperCachedOnly` (a4k raises TypeError on `None + ':'` and returns 0).

### Kodi update rule (Kodi 19+, from the Kodi source, Nexus/Omega/master)
- **Manual refresh:** the only trigger is the Add-ons screen header button "Check for updates" (add-on
  browser). There is no Settings entry and no per-repository context action. It refreshes all repositories.
- **What a refresh does:** for each repository Kodi fetches `addons.xml.md5` and compares it with the checksum
  stored in the addons DB. Equal: "checksum not changed", nothing downloaded. Different: Kodi downloads
  `addons.xml` and stores the new checksum.
- **Without `verify`** (repository.candre 1.0.0): Kodi stores the NEW md5 together with WHATEVER `addons.xml`
  it got. If the CDN served the new md5 with a stale `addons.xml`, the client stays on the old index until the
  md5 changes again (next publish), or the repository add-on is uninstalled/reinstalled, or its installed
  version changes.
- **With `<checksum verify="md5">`** (repository.candre 1.0.1): a mismatch fails the refresh ("index has wrong
  digest"), the stored checksum stays, and the next check retries cleanly.
- **Local DB only:** the Versions dialog and repository browsing read only the local addons DB, so they show
  nothing new until a refresh has stored it.
- **Automatic checks:** setting Settings > System > Add-ons > General > Updates (id `general.addonupdates`):
  "Install updates automatically" (default), "Notify, but don't install updates", "Never check for updates".
  Automatic checks run at the stored next-check time (default 24 h after the last result; Omega enforces at
  least 1 h between automatic runs). At startup Kodi checks only if that time has passed. It is NOT "at
  startup and every 24 h".
- **Origin:** an add-on auto-updates only from the repository it was installed from (its origin). A zip install
  of a regular add-on (Prism) has origin "" ("Manually installed") and is checked only against the official Kodi
  repo. A repository add-on uses its own id as origin, also when installed from a zip (`xbmc/addons/AddonInstaller.cpp`:
  "use own id as origin if repository"), so repository.candre updates itself. The info page shows
  no origin label; origin is visible only as the repository name under each entry in the Versions dialog
  (e.g. "5.0.59 / Candre Repository").
- **Switching origin** (no uninstall, settings kept): Prism info page > Versions > entry "5.0.59 / Candre
  Repository" > Install. Or Install from repository > Candre Repository > Prism, and answer No when asked
  about removing data.
- **GitHub Pages CDN:** `addons.xml`, `addons.xml.md5` and the zips are served with `Cache-Control: max-age=600`,
  and the CDN ignores query strings (`?v=` does not bust it). The two index files are separate CDN objects,
  updated seconds apart. After a publish, wait 10 min before "Check for updates".
- **1.0.0 clients update themselves to 1.0.1.** repository.candre 1.0.0 uses its own id as origin
  (`repository.candre`), so it auto-updates to 1.0.1 at the next successful refresh when Settings > System >
  Add-ons > General > Updates is "Install updates automatically" (the default). No manual zip install is needed.
  The 1.0.1 publish changes addons.xml.md5, so every client, including one stuck on a mismatched md5/index pair,
  downloads the full index again at its next check (a manual "Check for updates" at least 10 min after the
  publish, or the scheduled check). After 1.0.1 is installed, the installed repository version differs from the
  stored lastCheckedVersion, so the following check is a full fetch as well.
- **Stuck client, fallback only** (a client whose refresh still fails after the 1.0.1 publish: "Check for updates"
  changes nothing and the Versions dialog shows no new entry). Wait 10 min after the publish, then "Check for
  updates". Only if it still fails, install the 1.0.1 zip over the existing repository:
  1. Add-ons > Install from zip file > `repository.candre-1.0.1.zip` from https://cahitcangulec.github.io/candre/zips/repository.candre/
     (Unknown sources must be on; download the zip in a browser first if Kodi cannot browse the URL).
  2. "Check for updates" (not within 10 min of a publish).
  Last resort: uninstall Candre Repository first (My add-ons > Add-on repository > Candre Repository > Uninstall,
  answer No to removing data; this deletes its stored checksum row), then steps 1 and 2.

### Release flow (automatic since 2026-10-07)
1. Bump the version in `plugin.video.prism/addon.xml` (or `context.prism/` / `repository.candre/`).
2. Add a block at the top of `plugin.video.prism/changelog.txt`.
3. Commit on master and push master (`git push origin master`). Nothing else.
4. CI (`.github/workflows/publish-repo.yml`) checks out gh-pages in a worktree and runs
   `tools/build_repo.py . <worktree> HEAD --reuse-zips <worktree>`. If the tree changed, CI commits
   "Publish <addon> <version>" on gh-pages as github-actions[bot] and pushes it. The Pages step then waits
   for GitHub's automatic Pages build (polls `repos/.../pages/builds/latest`). It requests a build
   (POST `pages/builds`) only if none comes within 180 s or the automatic one errored, and it fails the run
   if the gh-pages tip is still not built after the wait. A red run means the site is stale: re-run it.
5. Kodi clients pick up the new addons.xml.md5 at their next check (automatic at the stored next-check time,
   or "Check for updates" at least 10 min after the publish) and update only addons whose origin is
   "Candre Repository" (see "Kodi update rule"). repository.candre itself updates too (its origin is its own id).
- Code pushed without a version bump is **not** published: the published zip for a version never
  changes, and the run shows a warning annotation. Bump the version to release.
- Manual run: GitHub -> Actions -> "Publish Kodi repository" -> Run workflow (master only).
- A run fails if gh-pages moved during the run (non-fast-forward push). Re-run it.
- Fallback without CI: build into the local gh-pages worktree, commit and push gh-pages (commands
  below). Fast-forward the worktree to origin/gh-pages first, because CI commits there.

---

## 📁 Active architecture

- **Stack:** Kodi Python 3 video addon (Kodi 20+/21/22), Seren lineage.
  - Entry `plugin.video.prism/prism.py`, routing `resources/lib/modules/router.py`.
  - Scraping/caching `modules/getSources.py`, debrid APIs `resources/lib/debrid/`.
  - Metadata via Simkl (`resources/lib/simkl/`).
- **Key modules:**
  - `modules/getSources.py` (Sources, TorrentCacheCheck: `_realdebrid_worker`, `_write_cache_results`,
    `_offer_unconfirmed_rd_torrents`, `RdCacheSummary`).
  - `modules/resolver/` (`Resolver`, `MAX_RESOLVE_ATTEMPTS`; RD torrent resolver stores probe results)
    and `debrid/real_debrid.py` (`check_hash` probe raising `modules/exceptions.TorrentNotCached`).
  - `debrid/external_cache.py` (DMM/Torrentio/Comet/AIOStreams RD/AD cache lookups, `_dmm_get_challenge`).
  - `database/debridCache` (hash cache rows: "True" 24 h, "False" 4 h; `clear_uncached_entries`).
  - `modules/prism_version.py` (version-change hooks).
  - `modules/cloud_scrapers.py`.
  - `common/source_utils.py` (release-name matching).
  - `modules/source_sorter.py` (`_get_cache_confidence_key`: verified > unverified > uncached).
- **Patterns:**
  - RD `/torrents/instantAvailability` is dead (RD disabled it late 2024). Cache verification goes
    through external services keyed on IMDb or `kitsu:<id>`.
  - DMM is the only per-hash checker. It needs a server-issued token: `GET /api/challenge` returns
    `{token, hash}`, sent as `dmmProblemKey`/`solution`. The token lives 5 min on the server
    (reused 110 s), the endpoint is IP rate-limited, and DMM is IMDb-only.
  - Torrentio, Comet and AIOStreams only report hashes in their own crowd caches.
  - RD: external answers only promote; only the resolver's RD probe writes "False" (4 h). Unconfirmed
    RD hashes are offered `unverified=True` and verified on play; uncached ones are skipped silently.
  - AD: a hash is persisted "False" only when DMM answered for it.

---

## ⚠️ External blockers (don't block coding)

- **Kodi on this machine.** Kodi userdata exists at `%APPDATA%\Kodi`: Seren 3.0.62 + a4kScrapers,
  kodi.log last written 2026-09-23, Prism not installed (the user tests Prism on another
  device). Whether Kodi actually runs here is unverified (the old "Kodi cannot run locally"
  note was never checked).
  - Until checked, verify with `python -m py_compile` and stubbed harnesses (stub `xbmc*`,
    `unidecode`, `globals.g`); the user tests inside Kodi.
- RD-keyed responses (`[RD+]` markers) need the user's RD token; never commit tokens.
- DMM `/api/challenge` is IP rate-limited; do not hammer it from harnesses.

---

## 🔧 Useful commands

```bash
python -m py_compile plugin.video.prism/resources/lib/modules/getSources.py   # syntax check (delete __pycache__ after)
git push origin master                                                       # release: CI rebuilds + pushes gh-pages
# fallback only (CI down): manual publish from a local gh-pages worktree
git worktree add ../candre-pages gh-pages                                    # once
git fetch origin && git -C ../candre-pages merge --ff-only origin/gh-pages   # take CI's commits first
python tools/build_repo.py . ../candre-pages master --reuse-zips ../candre-pages  # regenerate gh-pages
git -C ../candre-pages add -A && git -C ../candre-pages commit -m "Publish ..."
git push origin gh-pages
openwolf scan && openwolf status                                             # refresh the project index
gh run list -R cahitcangulec/candre --workflow publish-repo.yml --limit 3   # last Kodi publish runs; red = site may be stale
```

`gh` defaults to the upstream repo (Goldenfreddy0703/Prism) in this checkout: always pass `-R cahitcangulec/candre`.
`gh api` has no `-R`, so use the explicit `repos/cahitcangulec/candre/...` path there.

---

## 📚 References (read IF needed)

- `docs/rd-resolver-fallthrough.md`: 5.0.59 silent RD fall-through, promote-only hints, decision log, kodi.log lines
- `docs/rd-cache-dmm-fix.md`: 5.0.58 DMM auth / persisted-negatives investigation, verification, kodi.log lines
- `docs/anime-rd-cache-investigation.md`: 5.0.57 anime traced flow, root causes, verification, residual risks
- `.wolf/cerebrum.md`: User Preferences + Do-Not-Repeat + Decision Log
- `.wolf/anatomy.md`: token-efficient file index (local, regenerate with `openwolf scan`)
- `.wolf/buglog.json`: known bugs + fixes
