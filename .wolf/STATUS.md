# STATUS — candre

> Single source of truth for resuming work. Read this FIRST when starting a session.
> Update this file at the end of every work phase so the next `/clear` resumes in 1 read.
> Last updated: 2026-10-06 (late: 5.0.58 DMM fix)

---

## ✅ Done

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

**Goal:** the user confirms 5.0.58 in Kodi, then close the remaining open items.

### Open items (code paths relative to `plugin.video.prism/resources/lib/`)
1. **Confirm 5.0.58 in Kodi.** The user tested 5.0.57 in Kodi on another device; Lord of Mysteries
   was still all-uncached, which led to 5.0.58. 5.0.58 has not been tested yet.
   - 5.0.58 is published: origin/master 3db18dc and origin/gh-pages 3cc2944 (pushed 2026-10-06),
     so Kodi picks it up from https://cahitcangulec.github.io/candre/.
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

### Release flow
1. Bump the version in `plugin.video.prism/addon.xml`.
2. Add a block at the top of `plugin.video.prism/changelog.txt`.
3. Commit on master.
4. `python tools/build_repo.py . <gh-pages worktree>`.
5. Commit on gh-pages.
6. Push both branches (commands below).

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
git worktree add ../candre-pages gh-pages                                    # once, for publishing
python tools/build_repo.py . ../candre-pages master                          # regenerate zips + addons.xml + md5
git -C ../candre-pages add -A && git -C ../candre-pages commit -m "Publish ..."
git push origin master gh-pages
openwolf scan && openwolf status                                             # refresh the project index
```

---

## 📚 References (read IF needed)

- `docs/rd-cache-dmm-fix.md`: 5.0.58 DMM auth / persisted-negatives investigation, verification, kodi.log lines
- `docs/anime-rd-cache-investigation.md`: 5.0.57 anime traced flow, root causes, verification, residual risks
- `.wolf/cerebrum.md`: User Preferences + Do-Not-Repeat + Decision Log
- `.wolf/anatomy.md`: token-efficient file index (local, regenerate with `openwolf scan`)
- `.wolf/buglog.json`: known bugs + fixes
