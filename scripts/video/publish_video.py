"""Publish the approved walkthrough video to the site (P6 gate).

Copies both cuts from the git-ignored data/sources/video/out/ to site/public/video/,
converts their SRT captions to WebVTT (browsers read only WebVTT in <track>), and writes
the transcript as HTML into site/walkthrough.html between its transcript markers. The
outputs are committed: CI has no access to the video sources.

    uv run python -I scripts/video/publish_video.py [--check]

--check: exit 1 if the committed files differ from what the sources would give.
"""

from __future__ import annotations

import argparse
import html
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "data/sources/video/out"
OUT = ROOT / "site/public/video"
PAGE = ROOT / "site/walkthrough.html"
CUTS = ("curbcut-walkthrough", "curbcut-1min")
START, END = "<!-- transcript:start -->", "<!-- transcript:end -->"

# Working notes in the transcript that mean nothing to a reader of the site.
REPLACE = {
    " (recorded as act4a1 and act4a2)": "",
    "See `clips/nvda-transcript.md`.": "What NVDA says is below.",
}

TIME = re.compile(r"(\d\d:\d\d:\d\d),(\d\d\d)")


def srt_to_vtt(srt: str) -> str:
    cues = [c for c in srt.replace("\r\n", "\n").strip().split("\n\n") if c.strip()]
    out = ["WEBVTT", ""]
    for cue in cues:
        lines = cue.split("\n")
        if len(lines) < 3 or "-->" not in lines[1]:
            raise ValueError(f"not an SRT cue: {cue!r}")
        out += [lines[0], TIME.sub(r"\1.\2", lines[1]), *lines[2:], ""]
    return "\n".join(out)


def inline(text: str) -> str:
    text = html.escape(text, quote=False)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    return re.sub(r"\*([^*]+)\*", r"<em>\1</em>", text)


def transcript_html(md: str) -> str:
    for old, new in REPLACE.items():
        if old not in md:
            raise ValueError(f"transcript no longer contains {old!r}")
        md = md.replace(old, new)
    lines = md.replace("\r\n", "\n").split("\n")
    if not lines[0].startswith("# "):
        raise ValueError("transcript must start with its title")
    parts: list[str] = []
    i = 1
    while i < len(lines):
        line = lines[i].rstrip()
        if not line:
            i += 1
        elif line.startswith("## "):
            parts.append(f"<h3>{inline(line[3:])}</h3>")
            i += 1
        elif line.startswith("> NVDA: "):
            said = []
            while i < len(lines) and lines[i].startswith("> NVDA: "):
                said.append(lines[i][len("> NVDA: ") :].strip())
                i += 1
            parts.append(
                '<blockquote class="transcript-nvda"><p><span class="transcript-label">'
                f"NVDA:</span> {inline(' '.join(said))}</p></blockquote>"
            )
        elif line.startswith(("CAPTION: ", "Correction: ")):
            label, text = line.split(": ", 1)
            label = "On-screen caption" if label == "CAPTION" else "On-screen correction"
            when = ""
            if i + 1 < len(lines) and re.fullmatch(
                r"\((on screen|footnote on screen).*\)", lines[i + 1]
            ):
                when = f' <span class="transcript-when">{inline(lines[i + 1])}</span>'
                i += 1
            parts.append(
                f'<p class="transcript-screen"><span class="transcript-label">{label}:</span> '
                f"{inline(text)}{when}</p>"
            )
            i += 1
        else:
            para = []
            while (
                i < len(lines)
                and lines[i].strip()
                and not lines[i].startswith(("## ", "> ", "CAPTION: ", "Correction: "))
            ):
                para.append(lines[i].strip())
                i += 1
            parts.append(f"<p>{inline(' '.join(para))}</p>")
    return "\n".join(parts)


def outputs() -> dict[Path, bytes]:
    files: dict[Path, bytes] = {}
    for cut in CUTS:
        files[OUT / f"{cut}.mp4"] = (SRC / f"{cut}.mp4").read_bytes()
        srt = (SRC / f"{cut}.en.srt").read_text(encoding="utf-8")
        files[OUT / f"{cut}.en.vtt"] = srt_to_vtt(srt).encode("utf-8")
    page = PAGE.read_text(encoding="utf-8")
    if page.count(START) != 1 or page.count(END) != 1:
        raise ValueError(f"{PAGE.name} needs one {START} and one {END}")
    body = transcript_html((SRC / "curbcut-walkthrough-transcript.md").read_text(encoding="utf-8"))
    before, rest = page.split(START)
    _, after = rest.split(END)
    files[PAGE] = f"{before}{START}\n{body}\n{END}{after}".encode()
    return files


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Publish the walkthrough video to the site.")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    files = outputs()
    if args.check:
        stale = [p for p, b in files.items() if not p.exists() or p.read_bytes() != b]
        for p in stale:
            print(f"out of date: {p.relative_to(ROOT)}", file=sys.stderr)
        return 1 if stale else 0
    OUT.mkdir(parents=True, exist_ok=True)
    for path, data in files.items():
        if path.suffix == ".mp4":
            shutil.copyfile(SRC / path.name, path)
        else:
            path.write_bytes(data)
        print(f"wrote {path.relative_to(ROOT)} ({len(data):,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
