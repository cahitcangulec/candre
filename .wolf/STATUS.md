# STATUS — candre

> Single source of truth for resuming work. Read this FIRST when starting a session.
> Update this file at the end of every work phase so the next `/clear` resumes in 1 read.
> Last updated: 2026-10-06

---

## ✅ Done

- **2026-10-06 — Anime Real-Debrid fix (ce0d509, released as plugin.video.prism 5.0.57 in f7abc86).**
  Anime episodes showed 0 cached / 0 cloud RD sources. Fixed: RD cache check in
  `modules/getSources.py` was gated on an IMDb id (anime often has none); added Kitsu-id
  lookups (MAL/AniList -> Kitsu, `debrid/external_cache.py`) for Torrentio/Comet/AIOStreams;
  Seren-style unverified RD fallback for anime with no ids (`unverified=True`); anime
  zero-padded episode matcher (`- 05`, `05v2`) in `common/source_utils.py`; anime batch
  handling in `modules/cloud_scrapers.py`. Full write-up: `docs/anime-rd-cache-investigation.md`.
- **2026-10-06 — Kodi repository published.** `repository.candre` 1.0.0 (37aca8d); gh-pages
  serves addons.xml + zips at https://cahitcangulec.github.io/candre/ (gh-pages f2630d4).
- **2026-10-06 — Project brain.** OpenWolf 2.0.1 set up (Claude Code + Codex hooks), build
  script committed as `tools/build_repo.py`, investigation report as `docs/`.

---

## 🚀 Next phase

**Project:** candre = fork of Kodi addon Prism (upstream Goldenfreddy0703/Prism, a Seren fork),
https://github.com/cahitcangulec/candre. Branches: `master` = code, `gh-pages` = published
Kodi repo (https://cahitcangulec.github.io/candre/). Addons: `plugin.video.prism/` 5.0.57,
`context.prism/` 4.0.2, `repository.candre/` 1.0.0. Python 3; Kodi cannot run locally.

**Goal:** get the 5.0.57 anime RD fix confirmed in Kodi, then close the open items below.

### Open items (code paths relative to `plugin.video.prism/resources/lib/`)
1. **Unconfirmed in Kodi.** User has not yet verified 5.0.57 inside Kodi. Test hints:
   clear torrent cache first (Tools -> Clear Local Torrent Cache), look for `Anime cache check: Kitsu lookup`
   / `ExternalCache RD: N total cached hashes` in kodi.log (docs/anime-rd-cache-investigation.md section g).
2. **Unverified sources not sorted last.** Seren-style fallback sources carry `unverified=True`
   but `modules/source_sorter.py` `_get_sort_key_tuple` still sorts them like verified ones.
3. **TV season packs named "S01" never match in cloud.** Typo inherited from Seren:
   `season_fill_check = f"s%{season_fill}"` / `get_filter_season_pack_fn` in `common/source_utils.py`.

### Release flow
Bump version in `plugin.video.prism/addon.xml` -> add a line at the top of
`plugin.video.prism/changelog.txt` -> commit on master -> `python tools/build_repo.py . <gh-pages worktree>`
-> commit on gh-pages -> push both branches (commands below).

---

## 📁 Active architecture

- **Stack:** Kodi Python 3 video addon (Kodi 20+/21/22), Seren lineage. Entry `plugin.video.prism/prism.py`,
  routing `resources/lib/modules/router.py`, scraping/caching `modules/getSources.py`,
  debrid APIs `resources/lib/debrid/`, metadata via Simkl (`resources/lib/simkl/`).
- **Key modules:** `modules/getSources.py` (Sources, TorrentCacheCheck), `debrid/external_cache.py`
  (DMM/Torrentio/Comet/AIOStreams RD cache lookups), `modules/cloud_scrapers.py`,
  `common/source_utils.py` (release-name matching), `modules/source_sorter.py`.
- **Patterns:** RD `/torrents/instantAvailability` is dead (RD disabled it late 2024); cache
  verification goes through external services keyed on IMDb or `kitsu:<id>`.

---

## ⚠️ External blockers (don't block coding)

- Kodi is not available on this machine: verify with `python -m py_compile` and stubbed
  harnesses (stub `xbmc*`, `unidecode`, `globals.g`); the user tests inside Kodi.
- RD-keyed responses (`[RD+]` markers) need the user's RD token; never commit tokens.

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

- `docs/anime-rd-cache-investigation.md` — traced flow, root causes, verification, residual risks
- `.wolf/cerebrum.md` — User Preferences + Do-Not-Repeat + Decision Log
- `.wolf/anatomy.md` — token-efficient file index (local, regenerate with `openwolf scan`)
- `.wolf/buglog.json` — known bugs + fixes
