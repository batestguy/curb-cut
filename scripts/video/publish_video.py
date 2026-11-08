"""Publish the approved walkthrough video to the site (P6 gate).

Re-encodes both cuts from the git-ignored data/sources/video/out/ into smaller web copies
in site/public/video/ (x264 CRF 28, 96 kbps AAC, no embedded subtitle stream; the edit is
unchanged), converts their SRT captions to WebVTT, and writes the transcript as HTML into
site/walkthrough.html between its transcript markers. The outputs are committed: CI has no
access to the video sources.

WebVTT differs from the SRT in two ways:
- the correction footnotes are left out: they are burned into the picture already;
- every cue sits at 16% from the top (`line:16%`), below the burned-in correction band
  (about 3-15% of the height) and clear of the lower-third captions (78-92%).

    uv run python -I scripts/video/publish_video.py [--check] [--skip-encode]

--check: exit 1 if the committed captions or page differ from what the sources give, or a
web copy's duration differs from its source by more than 0.1 s.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import shutil
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "data/sources/video/out"
REPORT = ROOT / "data/sources/video/build/report.json"
OUT = ROOT / "site/public/video"
PAGE = ROOT / "site/walkthrough.html"
CUTS = ("curbcut-walkthrough", "curbcut-1min")
START, END = "<!-- transcript:start -->", "<!-- transcript:end -->"
CUE_SETTINGS = "line:16%"
ENCODE = [
    *["-map", "0:v:0", "-map", "0:a:0", "-c:v", "libx264", "-preset", "slow", "-crf", "28"],
    *["-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "96k", "-movflags", "+faststart"],
    *["-map_metadata", "-1"],
]

# Working notes in the transcript that mean nothing to a reader of the site.
REPLACE = {
    " (recorded as act4a1 and act4a2)": "",
    "See `clips/nvda-transcript.md`.": "What NVDA says is below.",
}
FIXES_NOTE = "Speech-recognition errors fixed in this transcript"

# What each shot shows (ids from make_video.py's ACTS and shots.mjs), for the transcript's
# "On screen" line under each part, in the order of the shots in the build report.
SHOWN = {
    "jonapwd": "the main page's section on JONAPWD's 2025 estimates, with its notice that they "
    "are built on an assumption",
    "jonapwd-chart": "the chart of JONAPWD's figures for all 37 states by type of disability",
    "home-top": "the top of the main page, with the national figure",
    "comparison": "the main page's section \u201cWhy you may see 15% or 3%\u201d",
    "meth-new": "the methodology page's \u201cWhat is new here, and what is not\u201d",
    "card-ndhs": "a card quoting the check that reproduces the official NDHS report tables",
    "card-svy": "a card quoting the cross-check of the estimates in R and Python",
    "dots": "the dot plot of disability by state, with 95% confidence intervals",
    "dots-findings": "the dot plot's statistical findings (73 comparisons checked, 20 supported)",
    "map": "the map of disability by state",
    "spatial": "the main page's section \u201cDo neighbouring states look alike?\u201d",
    "meth-fh": "the methodology page's section on the small-area model",
    "pov-top": "the top of the poverty page",
    "osf": "a card with the pre-registration on OSF (osf.io/kes3p)",
    "pov-headline-chart": "the poverty page's headline chart",
    "pov-refute": "the poverty page's \u201cChecks that should find nothing\u201d",
    "pov-sens": "the poverty page's \u201cHow strong would a hidden factor need to be?\u201d",
    "pov-bench": "the poverty page's \u201cCompared with factors we did measure\u201d",
    "pov-ghs": "the poverty page's exploratory GHS-Panel section",
    "pov-ghs-cons": "the GHS-Panel table's row for household consumption",
    "pov-dims": "the poverty page's chart of where the difference sits, by dimension",
    "code-lhci": "the Lighthouse CI settings that require an accessibility score of 100",
    "gha": "a passing GitHub Actions run",
    "pypi": "a card with the library's details on PyPI",
    "term-demo-0": "a terminal running the claim checker on the site's state chart",
    "term-demo-1": "the first claim and its verdict (passes)",
    "term-demo-2": "the second claim and its verdict (rejected)",
    "code-checker": "the claim checker's source code",
    "term-check": "a terminal running \u201cdisability-access-charts check --strict\u201d on every "
    "chart, passing",
}
SHOWN_ACT5 = "the main page, the state chart and the poverty page, at the part NVDA is reading"
ACT_IDS = {
    "Act 1": "act1",
    "Act 2": "act2",
    "Act 3": "act3",
    "Act 4": "act4",
    "Act 4b": "act4b",
    "Act 5": "act5",
    "Act 5b": "act5b",
    "Act 6": "act6",
}

TIME = re.compile(r"^(\d\d:\d\d:\d\d),(\d\d\d) --> (\d\d:\d\d:\d\d),(\d\d\d)$")


def _seconds(hms: str, ms: str) -> float:
    h, m, s = hms.split(":")
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000


def _norm(text: str) -> str:
    return " ".join(text.split())


def srt_to_vtt(srt: str, corrections: Sequence[str] = ()) -> str:
    """WebVTT from SRT, without the correction footnotes (burned in already).

    A footnote is a cue starting "Correction:" plus the cues that continue its text while it
    is on screen (make_video.py splits a long footnote over several cues)."""
    cues = []
    for block in [c for c in srt.replace("\r\n", "\n").strip().split("\n\n") if c.strip()]:
        lines = block.split("\n")
        m = TIME.match(lines[1]) if len(lines) >= 3 else None
        if not m:
            raise ValueError(f"not an SRT cue: {block!r}")
        text = lines[2:]
        if any("-->" in t for t in text):
            raise ValueError(f"cue text contains '-->': {block!r}")
        cues.append((_seconds(m[1], m[2]), _seconds(m[3], m[4]), lines[1], text))
    notes = [_norm(c) for c in corrections]
    windows = []  # (start, end, full footnote text)
    for start, end, _, text in cues:
        joined = _norm(" ".join(text))
        if joined.startswith("Correction:"):
            full = next((n for n in notes if n.startswith(joined)), None)
            if full is None:
                raise ValueError(f"footnote cue matches no known correction: {joined!r}")
            windows.append((start, end, full))
    out = ["WEBVTT", ""]
    n = 0
    for start, _, timing, text in cues:
        joined = _norm(" ".join(text))
        if joined.startswith("Correction:"):
            continue
        if any(w0 <= start <= w1 + 0.5 and joined in full for w0, w1, full in windows):
            continue
        n += 1
        body = [html.escape(t, quote=False) for t in text]
        out += [str(n), f"{timing.replace(',', '.')} {CUE_SETTINGS}", *body, ""]
    return "\n".join(out)


def inline(text: str) -> str:
    text = html.escape(text, quote=False)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    return re.sub(r"\*(?=\S)([^*]*?\S)\*", r"<em>\1</em>", text)


def shown_line(act: str | None, report: dict | None) -> str:
    if act is None or report is None:
        return ""
    if act == "act5":
        items = [SHOWN_ACT5]
    else:
        items = []
        for item in report["acts"][act]["timeline"]:
            if "shot" not in item:
                continue
            if item["shot"] not in SHOWN:
                raise ValueError(f"no description for shot {item['shot']!r}")
            if SHOWN[item["shot"]] not in items:
                items.append(SHOWN[item["shot"]])
    text = "; ".join(items)
    return (
        '<p class="transcript-shown"><span class="transcript-label">On screen:</span> '
        f"{inline(text[0].upper() + text[1:])}.</p>"
    )


def transcript_html(md: str, report: dict | None = None) -> str:
    for old, new in REPLACE.items():
        if old not in md:
            raise ValueError(f"transcript no longer contains {old!r}")
        md = md.replace(old, new)
    lines = md.replace("\r\n", "\n").split("\n")
    if not lines[0].startswith("# "):
        raise ValueError("transcript must start with its title")
    starts = ("## ", ">", "CAPTION: ", "Correction: ")
    parts: list[str] = []
    i = 1
    while i < len(lines):
        line = lines[i].rstrip()
        if not line:
            i += 1
        elif line.startswith("## "):
            title = line[3:]
            parts.append(f"<h3>{inline(title)}</h3>")
            if shown := shown_line(ACT_IDS.get(title.split(":")[0].strip()), report):
                parts.append(shown)
            i += 1
        elif line.startswith(">"):
            said, other = [], []
            while i < len(lines) and lines[i].startswith(">"):
                body = lines[i][1:].strip()
                if body.startswith("NVDA:"):
                    said.append(body[len("NVDA:") :].strip())
                else:
                    other.append(body)
                i += 1
            if said:
                parts.append(
                    '<blockquote class="transcript-nvda"><p><span class="transcript-label">'
                    f"NVDA:</span> {inline(' '.join(said))}</p></blockquote>"
                )
            if other:
                parts.append(f"<blockquote><p>{inline(' '.join(other))}</p></blockquote>")
        elif line.startswith(("CAPTION: ", "Correction: ")):
            label, text = line.split(": ", 1)
            label = "On-screen caption" if label == "CAPTION" else "On-screen correction"
            when = ""
            nxt = lines[i + 1] if i + 1 < len(lines) else ""
            if re.fullmatch(r"\((on screen|footnote on screen).*\)", nxt):
                when = f' <span class="transcript-when">{inline(nxt)}</span>'
                i += 1
            parts.append(
                f'<p class="transcript-screen"><span class="transcript-label">{label}:</span> '
                f"{inline(text)}{when}</p>"
            )
            i += 1
        else:
            para = [line.strip()]  # always consume this line
            i += 1
            while i < len(lines) and lines[i].strip() and not lines[i].startswith(starts):
                para.append(lines[i].strip())
                i += 1
            text = " ".join(para)
            if text.startswith(FIXES_NOTE):
                parts.append(
                    "<details><summary>Speech-recognition fixes in this transcript</summary>"
                    f"<p>{inline(text)}</p></details>"
                )
            else:
                parts.append(f"<p>{inline(text)}</p>")
    return "\n".join(parts)


def corrections(md: str) -> list[str]:
    return [line for line in md.splitlines() if line.startswith("Correction: ")]


def duration(path: Path) -> float:
    ffprobe = shutil.which("ffprobe") or "ffprobe"  # Windows: a bare name can fail here
    out = subprocess.run(
        [ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        check=True,
        capture_output=True,
        text=True,
    )
    return float(out.stdout.strip())


def text_outputs() -> dict[Path, str]:
    md = (SRC / "curbcut-walkthrough-transcript.md").read_text(encoding="utf-8")
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    files: dict[Path, str] = {}
    for cut in CUTS:
        srt = (SRC / f"{cut}.en.srt").read_text(encoding="utf-8")
        files[OUT / f"{cut}.en.vtt"] = srt_to_vtt(srt, corrections(md))
    page = PAGE.read_text(encoding="utf-8")
    if page.count(START) != 1 or page.count(END) != 1:
        raise ValueError(f"{PAGE.name} needs one {START} and one {END}")
    before, rest = page.split(START)
    _, after = rest.split(END)
    files[PAGE] = f"{before}{START}\n{transcript_html(md, report)}\n{END}{after}"
    return files


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Publish the walkthrough video to the site.")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--skip-encode", action="store_true", help="keep the current MP4s")
    args = parser.parse_args(argv)
    files = text_outputs()
    if args.check:
        bad = [
            str(p.relative_to(ROOT))
            for p, t in files.items()
            if not p.exists() or p.read_text(encoding="utf-8") != t
        ]
        for cut in CUTS:
            web = OUT / f"{cut}.mp4"
            if not web.exists() or abs(duration(web) - duration(SRC / f"{cut}.mp4")) > 0.1:
                bad.append(str(web.relative_to(ROOT)))
        for p in bad:
            print(f"out of date: {p}", file=sys.stderr)
        return 1 if bad else 0
    OUT.mkdir(parents=True, exist_ok=True)
    if not args.skip_encode:
        for cut in CUTS:
            web = OUT / f"{cut}.mp4"
            src = str(SRC / f"{cut}.mp4")
            ffmpeg = shutil.which("ffmpeg") or "ffmpeg"
            subprocess.run([ffmpeg, "-v", "error", "-y", "-i", src, *ENCODE, str(web)], check=True)
            print(f"wrote {web.relative_to(ROOT)} ({web.stat().st_size:,} bytes)")
    for path, text in files.items():
        path.write_text(text, encoding="utf-8", newline="\n")
        print(f"wrote {path.relative_to(ROOT)} ({len(text.encode()):,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
