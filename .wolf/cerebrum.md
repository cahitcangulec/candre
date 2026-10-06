# Cerebrum

> OpenWolf's learning memory. Updated automatically as the AI learns from interactions.
> Do not edit manually unless correcting an error.
> Last updated: 2026-10-06

## User Preferences

<!-- How the user likes things done. Code style, tools, patterns, communication. -->

- Releases go to the user's own Kodi repository on gh-pages (https://cahitcangulec.github.io/candre/), not upstream.
- Every user-visible fix gets a version bump in `plugin.video.prism/addon.xml` plus a `changelog.txt` line (`[BUG] ...` style, newest on top).

## Key Learnings

- **Project:** candre, a fork of the Kodi video addon Prism (upstream https://github.com/Goldenfreddy0703/Prism, itself a Seren fork). Fork: https://github.com/cahitcangulec/candre. Remotes: `origin` = fork, `upstream` = Prism.
- **Layout:** `plugin.video.prism/` (main addon), `context.prism/` (context menu), `repository.candre/` (Kodi repository addon). The root `addon.xml` is an upstream symlink stored as a text file; the real manifest is `plugin.video.prism/addon.xml`.
- **Kodi cannot run locally.** Verify with `python -m py_compile` and stubbed harnesses (stub `xbmc*`, `unidecode`, `resources.lib.modules.globals.g`), remove `__pycache__` afterwards, and ask the user to confirm in Kodi.
- **Publishing:** `tools/build_repo.py <repo> <out> [ref]` packages committed git blobs of the ref (default master), not the working tree. Commit first, then build into a gh-pages worktree. It reproduces the published addons.xml md5 byte-for-byte.
- **RD cache checks:** RD `/torrents/instantAvailability` is dead (disabled late 2024). Prism verifies cache via external services (DMM, Torrentio, Comet, AIOStreams) in `debrid/external_cache.py`, keyed on IMDb or `kitsu:<id>`. Torrentio/Comet accept `kitsu:` ids; DMM is IMDb-only.
- **Anime metadata:** IMDb ids come only from Simkl and are often missing for anime (especially sequel cours). MAL/AniList/Kitsu ids and native `anime_episode` numbering are available on the item.
- **Cloud sources:** RD cloud inspection only lists the newest 100 torrents in the account, and `rd.autodelete` defaults to true, so 0 cloud sources is often correct.
- **debridCache:** hashes written as "False" (uncached) are not rechecked for 4 h; clear the torrent cache when testing cache fixes.

## Do-Not-Repeat

<!-- Mistakes made and corrected. Each entry prevents the same mistake recurring. -->
<!-- Format: [YYYY-MM-DD] Description of what went wrong and what to do instead. -->

- [2026-10-06] RD cache verification was gated on an IMDb id, so anime without IMDb showed 0 cached. Any id-gated lookup must also handle anime ids (Kitsu via MAL/AniList) and must not persist never-checked hashes as "uncached".
- [2026-10-06] Anime release names ("[Group] Show - 05", batches "(01-12)") do not follow SxxEyy; title-anchored regexes and unpadded needles miss them. Test matchers against fansub naming.

## Decision Log

<!-- Significant technical decisions with rationale. Why X was chosen over Y. -->

- [2026-10-06] Anime episodes with neither IMDb nor Kitsu id get Seren-style unverified RD sources (`unverified=True`, verified by the resolver on play) instead of showing 0. Sorting them after verified sources is still open.
- [2026-10-06] Kodi repository is served from the `gh-pages` branch via GitHub Pages and built from git blobs by `tools/build_repo.py` (deterministic addons.xml, no working-tree leakage).
- [2026-10-06] OpenWolf brain files (STATUS, cerebrum, buglog, config, hooks) are committed; per-machine state (anatomy index, memory log, token ledger, session/daemon/cron state, dashboard token, `.codex/hooks.json` with absolute paths) is gitignored.
