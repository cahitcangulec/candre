# STATUS — candre

> Single source of truth for resuming work. Read this FIRST when starting a session.
> Update this file at the end of every work phase so the next `/clear` resumes in 1 read.
> Last updated: 2026-10-07 (5.0.58 live after a manual Pages build; Kodi origin rule)

---

## ✅ Done

- **2026-10-07 — plugin.video.prism 5.0.58 is live (deployed 2026-10-06 23:59 UTC).**
  - A manual Pages build request (`gh api -X POST repos/cahitcangulec/candre/pages/builds`,
    2026-10-06 23:58:47 UTC, HTTP 201) built gh-pages 3cc2944 in 23 s.
  - https://cahitcangulec.github.io/candre/ serves addons.xml with plugin.video.prism 5.0.58
    (addons.xml.md5 `1aef23e379d972cb215dc53b7eef877c`) and
    `zips/plugin.video.prism/plugin.video.prism-5.0.58.zip` (HTTP 200, 8596527 bytes). No CDN lag.
- **2026-10-07 — Automatic publishing (committed on master, not pushed yet).**
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
- Addons: `plugin.video.prism/` 5.0.58, `context.prism/` 4.0.2, `repository.candre/` 1.0.0. Python 3.

**Goal:** push master (the first "Publish Kodi repository" run must succeed; 5.0.58 is already
live, so it should find nothing to publish), then the user sets Prism's origin to Candre Repository
and confirms 5.0.58 in Kodi, then close the remaining open items.

### Open items (code paths relative to `plugin.video.prism/resources/lib/`)
1. **Confirm 5.0.58 in Kodi.** The user tested 5.0.57 in Kodi on another device; Lord of Mysteries
   was still all-uncached, which led to 5.0.58. 5.0.58 has not been tested yet.
   - 5.0.58 is live at https://cahitcangulec.github.io/candre/ (gh-pages 3cc2944, deployed
     2026-10-06 23:59 UTC after a manual Pages build request).
   - Kodi only auto-updates Prism if its origin is "Candre Repository" (see "Kodi update rule").
   - Install 5.0.58. The version change purges stale negatives by itself; kodi.log shows
     `Clearing uncached debrid hashes on Prism version change` and `DebridCache: Cleared N uncached entries`.
     Alternatively use Tools -> Clear Local Torrent Cache.
   - Enable debug logging and scrape Lord of Mysteries S01E01.
   - Expect `ExternalCache: DMM RD returned N cached hashes (checked X of Y)` and
     `ExternalCache RD: N total cached hashes (DMM answered for X of Y)` with X > 0.
   - Expect **no** `DMM RD check failed: 403`.
   - If DMM is down, expect `RD cache check: DMM availability check unreachable (no answer), offering N torrents
     unverified`; those sources show "(Unverified)" and sort last.
   - Anime-specific lines from 5.0.57: `docs/anime-rd-cache-investigation.md` section g.
2. **Hard-coded Torrentio fallback key.**
   - `debrid/external_cache.py` `_TIO_FALLBACK_PARAM` embeds a third-party Real-Debrid API key,
     used when `rd.auth` is empty. It is inherited from upstream.
   - Decide whether to remove it (Torrentio check needs the user's token) or keep it. Never copy
     the key into docs or logs.
3. **a4kScrapers `apikeys` (low value).** `modules/getSources.py` `_get_provider_sources` could pass
   `apikeys={'rd': ...}` (behind `try/except TypeError`) so Torrentio returns `[RD+]`. Prism now
   honours the resulting `debrid == "RD"` marker. This duplicates `torrentio_check_cache`.
4. **DMM is not ground truth.** DMM is a crowd DB keyed by IMDb id. Hashes it reports as
   unavailable are still stored "False" for 4 h. If users report false "uncached" results,
   consider a shorter negative TTL, or offering DMM-negative RD hashes as unverified too.

### Kodi update rule (Kodi 19+, from Kodi source `xbmc/addons/AddonRepos.cpp`)
- An addon auto-updates only from the repository it was installed from (its origin). A zip install
  has origin "" ("Manual" on its info page) and is checked only against the official Kodi repo.
- So the user's Prism needs Origin = "Candre Repository". One-time fix: Prism info page -> Versions
  -> newest entry labelled "Candre Repository" (keeps settings), or Install from repository ->
  Candre Repository -> Prism (answer No to removing settings).
- Then the default "Install updates automatically" applies: checks at startup and every 24 h, or on
  demand via Add-on browser -> Check for updates.

### Release flow (automatic since 2026-10-07)
1. Bump the version in `plugin.video.prism/addon.xml` (or `context.prism/` / `repository.candre/`).
2. Add a block at the top of `plugin.video.prism/changelog.txt`.
3. Commit on master and push master (`git push origin master`). Nothing else.
4. CI (`.github/workflows/publish-repo.yml`) checks out gh-pages in a worktree and runs
   `tools/build_repo.py . <worktree> HEAD --reuse-zips <worktree>`. If the tree changed, CI commits
   "Publish <addon> <version>" on gh-pages as github-actions[bot] and pushes it. If GitHub Pages
   is not serving the gh-pages tip, CI requests a Pages build.
5. Kodi installs with `repository.candre` see the new addons.xml.md5 and update by themselves, but
   only for addons whose origin is "Candre Repository" (see "Kodi update rule").
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
    `_offer_unanswered_rd_torrents`).
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
  - A hash is persisted "False" only when DMM answered for it.
  - Unanswered RD hashes are offered `unverified=True` (the resolver verifies on play).

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
```

---

## 📚 References (read IF needed)

- `docs/rd-cache-dmm-fix.md`: 5.0.58 DMM auth / persisted-negatives investigation, verification, kodi.log lines
- `docs/anime-rd-cache-investigation.md`: 5.0.57 anime traced flow, root causes, verification, residual risks
- `.wolf/cerebrum.md`: User Preferences + Do-Not-Repeat + Decision Log
- `.wolf/anatomy.md`: token-efficient file index (local, regenerate with `openwolf scan`)
- `.wolf/buglog.json`: known bugs + fixes
