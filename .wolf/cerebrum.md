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
- **Verification without Kodi:** use `python -m py_compile` and stubbed harnesses (stub `xbmc*`, `unidecode`, `resources.lib.modules.globals.g`), remove `__pycache__` afterwards, and ask the user to confirm in Kodi.
- **Kodi userdata on this machine:** `%APPDATA%\Kodi` exists with Seren 3.0.62 + a4kScrapers (kodi.log last written 2026-09-23); Prism is not installed there, and the user tests Prism in Kodi on another device. The older note "Kodi cannot run locally" was never verified, so check before assuming it.
- **Publishing:** `tools/build_repo.py <repo> <out> [ref] [--reuse-zips <dir>]` packages committed git blobs of the ref (default master), not the working tree. It reproduces the published addons.xml md5 byte-for-byte. Since 2026-10-07 CI (`.github/workflows/publish-repo.yml`) runs it on every addon push to master and pushes gh-pages, so a release needs only version bump + changelog + `git push origin master`. `--reuse-zips` keeps an already-published `<addon>-<version>.zip` byte for byte. Zips rebuilt from the same commit are byte-identical only with the same zlib (Python 3.11 zlib 1.3.1 and Python 3.14 zlib-ng differ).
- **A gh-pages push does not guarantee a Pages deploy:** the 2026-10-06 push of gh-pages 3cc2944 never started a "pages build and deployment" run, so Pages kept serving f2630d4 (5.0.57). After publishing, compare `gh api repos/cahitcangulec/candre/pages/builds/latest` (commit) or the live addons.xml with the gh-pages tip. The CI workflow requests a build when they differ.
- **RD cache checks:** RD `/torrents/instantAvailability` is dead (disabled late 2024). Prism verifies cache via external services (DMM, Torrentio, Comet, AIOStreams) in `debrid/external_cache.py`, keyed on IMDb or `kitsu:<id>`. Torrentio/Comet accept `kitsu:` ids; DMM is IMDb-only.
- **Anime metadata:** IMDb ids come only from Simkl and are often missing for anime (especially sequel cours). MAL/AniList/Kitsu ids and native `anime_episode` numbering are available on the item.
- **Cloud sources:** RD cloud inspection only lists the newest 100 torrents in the account, and `rd.autodelete` defaults to true, so 0 cloud sources is often correct.
- **debridCache:** hashes written as "False" (uncached) are not rechecked for 4 h; clear the torrent cache when testing cache fixes. Since 5.0.58 every version change purges the "False" rows (`prism_version` -> `DebridCache.clear_uncached_entries`).
- **DMM challenge token (since 2026-08-31):** DMM signs availability tokens server-side. `GET https://debridmediamanager.com/api/challenge` returns `{token, hash}`, which is sent as `dmmProblemKey` / `solution` to `/api/availability/check` (RD) and `/api/availability/ad/check` (AD). Server TTL is 5 min (Prism reuses a token for 110 s), the endpoint is IP rate-limited, and each request accepts at most 100 hashes. The old client-side signing with a hard-coded salt now gets `403 {"errorMessage":"Authentication error"}`.
- **Only DMM is hash-authoritative:** DMM answers for an arbitrary hash list (filtered by IMDb id). Torrentio, Comet and AIOStreams only return hashes from their own crowd caches for that id, so a hash missing from them is not evidence of "uncached". DMM itself is a crowd DB too, so it is not ground truth either.
- **Seren's "cached" is not a check:** Seren 3.0.62 `_realdebrid_worker` (getSources.py ~1164) sets `debrid_provider='real_debrid'` on every scraped torrent, and the resolver finds out on play ("Failed to resolve source"). Do not use Seren's cached count as a reference for Prism's accuracy.
- **a4kScrapers torrentio** queries Torrentio without a debrid key unless `apikeys` is passed to `episode()`/`movie()`. Neither Seren nor Prism passes it, so a4k results carry no `[RD+]` / `debrid='RD'` marker.
- **Comet** answers HTTP 200 with a single "[❌] ..." error stream (e.g. "Invalid API key") instead of an error status. Treat that as no answer and try the next base.

## Do-Not-Repeat

<!-- Mistakes made and corrected. Each entry prevents the same mistake recurring. -->
<!-- Format: [YYYY-MM-DD] Description of what went wrong and what to do instead. -->

- [2026-10-06] RD cache verification was gated on an IMDb id, so anime without IMDb showed 0 cached. Any id-gated lookup must also handle anime ids (Kitsu via MAL/AniList) and must not persist never-checked hashes as "uncached".
- [2026-10-06] Anime release names ("[Group] Show - 05", batches "(01-12)") do not follow SxxEyy; title-anchored regexes and unpadded needles miss them. Test matchers against fansub naming.
- [2026-10-06] Never persist a hash as uncached unless a hash-authoritative service (DMM, or the debrid's own hash-check API) actually answered for that hash. Persisting failed or unanswered checks as "False" hid every DMM-only release for 4 h per scrape.
- [2026-10-06] When a third-party API silently returns 403, an error payload or an empty result, treat it as "no answer", not as a negative. Checkers must return `None` for no answer and `set()` only for a real answer. The DMM 403 went unnoticed for five weeks because it was swallowed as an empty set.
- [2026-10-06] An unquoted Bash heredoc (`<<EOF`) runs backtick and `$(...)` command substitution inside the text. Writing a STATUS line containing a backticked `git push ...` that way executed the push. Always quote heredoc delimiters (`<<'EOF'`) when the text holds backticks, and pass paths as arguments instead of interpolating them.
- [2026-10-06] The 5.0.57 anime fix grew out of a generic hypothesis (no IMDb id) and did not fix the user's actual case. Lord of Mysteries has IMDb and Kitsu ids, so that code path never ran. Before concluding, reproduce the reported title live: its ids, the scraper output, and each external service separately.

## Decision Log

<!-- Significant technical decisions with rationale. Why X was chosen over Y. -->

- [2026-10-06] Anime episodes with neither IMDb nor Kitsu id get Seren-style unverified RD sources (`unverified=True`, verified by the resolver on play) instead of showing 0. (Superseded and extended in 5.0.58, see below.)
- [2026-10-06] 5.0.58: an RD torrent that no service confirmed **and** DMM did not answer for (DMM down or rate-limited, a Kitsu-only lookup, or more hashes than were answered) is offered as unverified (`unverified=True`, label "REAL DEBRID (UNVERIFIED)", string #31129), not hidden as uncached. `source_sorter._get_cache_confidence_key` sorts verified/cloud/hoster/direct (2) > unverified (1) > plain uncached torrent (0), ahead of the user's sort methods. Rationale: Seren parity without lying; verified sources still win.
- [2026-10-06] 5.0.58: every addon version change purges `cached='False'` debridCache rows (`prism_version.do_version_change` -> `DebridCache.clear_uncached_entries`). Rationale: a release that fixes a cache check must not inherit up to 4 h of wrong negatives from the old version. Cost: one extra round of checks after each update.
- [2026-10-06] 5.0.58: Comet bases that answer with only "[❌]" error streams (e.g. "Invalid API key") are skipped and the next base is tried. Previously the first 2xx base ended the loop.
- [2026-10-06] Kodi repository is served from the `gh-pages` branch via GitHub Pages and built from git blobs by `tools/build_repo.py` (deterministic addons.xml, no working-tree leakage).
- [2026-10-07] gh-pages is published by GitHub Actions (`publish-repo.yml`) with plain git in a worktree, not peaceiris/actions-gh-pages. Reason: the build needs the current gh-pages tree for `--reuse-zips`, and plain git gives the no-change check and the commit message without a third-party action holding a write token. A published version's zip is immutable; code pushed without a version bump is not published.
- [2026-10-06] OpenWolf brain files (STATUS, cerebrum, buglog, config, hooks) are committed; per-machine state (anatomy index, memory log, token ledger, session/daemon/cron state, dashboard token, `.codex/hooks.json` with absolute paths) is gitignored.
