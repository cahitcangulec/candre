<!-- openwolf:begin -->
# OpenWolf

@.wolf/OPENWOLF.md

This project uses OpenWolf for context management. Read and follow .wolf/OPENWOLF.md every session. Check .wolf/cerebrum.md before generating code. Check .wolf/anatomy.md before reading files.
<!-- openwolf:end -->

## Project: candre (Kodi addon fork)

- Fork of the Kodi addon Prism (upstream https://github.com/Goldenfreddy0703/Prism, a Seren fork); fork at https://github.com/cahitcangulec/candre. `master` = code, `gh-pages` = published Kodi repository at https://cahitcangulec.github.io/candre/.
- Addons: `plugin.video.prism/`, `context.prism/`, `repository.candre/`. Python 3. Kodi cannot run on this machine: verify with `python -m py_compile` and stubbed harnesses, then let the user test in Kodi.
- Current state, open items and the release flow: `.wolf/STATUS.md`. Repo build script: `tools/build_repo.py`. Background on the anime Real-Debrid fix: `docs/anime-rd-cache-investigation.md`.
