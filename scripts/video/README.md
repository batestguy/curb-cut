# Walkthrough video tooling (P6 gate)

Scripts for the narrated walkthrough video. Every input and output lives in the
git-ignored `data/sources/video/` (script, the author's voice files, the NVDA
recording, cards, clips); nothing here is published until the author approves the cut.

| Script | What it does |
|---|---|
| `check_numbers.py` | Checks every number and claim in `script.md` (and later the transcript and SRT) against the live site's JSON and the committed P5 CSVs; exit 1 on any mismatch or unchecked caption number. `--local` reads `site/public/data` instead. |
| `rec.mjs` (+ `loopback.py`) | Records NVDA reading the live site (Guidepup + Playwright, NVDA's default rate for the session; GoatCounter blocked) with WASAPI loopback audio and a timed speech log, into `data/sources/video/rec/`. Needs NVDA via Guidepup, Windows, and must run outside Claude Code's sandbox (window focus). |
| `cards.mjs` | Renders the lower-third scene cards (site colours) and checks their contrast with axe. |
| `make_act5.py` | Cuts act 5 from the recording: cut points from the speech log and the audio envelope, cards, crossfades, loudness to -16 LUFS. |
| `demo_library.py` | Act 5b: `disability-access-charts`'s claim checker on the real state chart. |

```
cd scripts/video && npm ci
node rec.mjs
node cards.mjs
cd ../.. && uv run python -I scripts/video/make_act5.py
uv run python -I scripts/video/check_numbers.py
uv run python -I scripts/video/demo_library.py
```

On 2026-11-07 the connection ran at about 18 KB/s, too slow for DuckDB-WASM's 34 MB
engine to start within the site's 90-second limit, so `rec.mjs` serves the four DuckDB
engine files from the local build after checking that their sizes match the live files.
Every figure still comes from the live site.
