# Walkthrough video tooling (P6 gate)

Scripts for the narrated walkthrough video. Every input and output lives in the
git-ignored `data/sources/video/` (script, the author's voice files, the NVDA
recording, cards, clips); nothing here is published until the author approves the cut.

| Script | What it does |
|---|---|
| `check_numbers.py` | Checks every number and claim in `script.md` (and the transcript and SRT; numbers on `CAPTION:` and `Correction:` lines must all be covered) against the live site's JSON and the committed P5 CSVs; exit 1 on any mismatch or unchecked caption number. `--local` reads `site/public/data` instead. |
| `rec.mjs` (+ `loopback.py`) | Records NVDA reading the live site (Guidepup + Playwright, NVDA's default rate for the session; GoatCounter blocked) with WASAPI loopback audio and a timed speech log, into `data/sources/video/rec/`. Needs NVDA via Guidepup, Windows, and must run outside Claude Code's sandbox (window focus). |
| `cards.mjs` | Renders the lower-third scene cards (site colours) and checks their contrast with axe. |
| `make_act5.py` | Cuts act 5 from the recording: cut points from the speech log and the audio envelope, cards, crossfades, loudness to -16 LUFS. |
| `demo_library.py` | Act 5b: `disability-access-charts`'s claim checker on the real state chart. |
| `make_video.py` | Assembles `out/curbcut-walkthrough.mp4` and `out/curbcut-1min.mp4` (acts 1–2) from the author's voice files (`voice/*.aac`) and act 5: speech trimmed to 0.4 s margins, each act at -16 LUFS (TP -1.5), shots cut on the spoken words with a slow zoom, the script's `CAPTION:` lines and four correction footnotes timed to the words, 0.5 s crossfades; writes closed captions (`.en.srt`, also muxed as a `mov_text` track) and a transcript. Never runs the scripts that read restricted data: `validate_ndhs` and `crosscheck_svy` appear as cards quoting `docs/verification.md`. `--no-shots` reuses the stills. |
| `shots.mjs` | Run by `make_video.py`: screenshots of the site from the local build under the live URL (after checking the pages and data files match the live site), PyPI/OSF/GitHub Actions live where they load (else a card from their public APIs or `gh run view`), terminal and code cards, captions and footnotes; axe contrast check on every card. |
| `whisper_words.py` | Word timestamps of the voice files with faster-whisper `small.en` (local, CPU), cached in `build/words.json`. |

```
cd scripts/video && npm ci
node rec.mjs
node cards.mjs
cd ../.. && uv run python -I scripts/video/make_act5.py
uv run python -I scripts/video/check_numbers.py
uv run python -I scripts/video/demo_library.py
uv run python -I scripts/video/make_video.py
uv run python -I scripts/video/check_numbers.py data/sources/video/script.md data/sources/video/out/curbcut-walkthrough.en.srt data/sources/video/out/curbcut-walkthrough-transcript.md
```

On 2026-11-07 the connection ran at about 18 KB/s, too slow for DuckDB-WASM's 34 MB
engine to start within the site's 90-second limit, so `rec.mjs` serves the four DuckDB
engine files from the local build after checking that their sizes match the live files.
Every figure still comes from the live site.

`make_video.py` needs ffmpeg, the local site build (`site/dist`, from `cd site && npm run build`)
and, the first time, faster-whisper's `small.en` model at `D:/models/faster-whisper-small.en`
(or `$WHISPER_MODEL`); it never downloads a model. PyPI shows automated browsers a challenge
page, so its card is filled from PyPI's JSON API instead of a screenshot.
