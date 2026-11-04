"""Build the self-hosted Noto Sans subset for Nigerian-language text (P6 item 5, D29).

Atkinson Hyperlegible Next lacks the Yoruba, Hausa and Igbo letters and the naira sign; Noto
Sans covers them all, with mark positioning for stacked tone marks (D29). The site uses the
subset only for text marked lang="yo", "ha", "ig" or "pcm" (site/src/style.css), so English
pages download nothing extra.

Source: Noto Sans variable font from google/fonts at a pinned commit, checked by SHA-256 and
kept in git-ignored data/sources/fonts/. Output (committed): site/public/fonts/
noto-sans-nigeria.woff2 (width 100, weight 400-700) and the font's OFL.txt beside it.

    uv run python packages/transform/scripts/make_font_subset.py [--download]
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import sys
import tempfile
import urllib.request
from pathlib import Path

from fontTools import subset
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

ROOT = Path(__file__).resolve().parents[3]
SOURCE_DIR = ROOT / "data" / "sources" / "fonts"
OUT_DIR = ROOT / "site" / "public" / "fonts"
OUT_NAME = "noto-sans-nigeria.woff2"

COMMIT = "2984c575fdce412ee02b2baaba67672b9a9434d8"  # google/fonts, 2024-11-20
RAW = f"https://raw.githubusercontent.com/google/fonts/{COMMIT}/ofl/notosans"
SOURCES = {
    "NotoSans[wdth,wght].ttf": (
        f"{RAW}/NotoSans%5Bwdth,wght%5D.ttf",
        "bfb7bb691513f12e734dc346c03a03f784912432d7e3fa8e56efcf906fe86b3d",
    ),
    "OFL.txt": (f"{RAW}/OFL.txt", None),
}

# Characters the subset must cover (tests/test_font_subset.py checks each one).
REQUIRED = (
    "ẹẸọỌṣṢ̣̀́àáèéìíòóùúÀÁÈÉÌÍÒÓÙÚńŃǹǸ"  # Yoruba
    "ɓƁɗƊƙƘƴƳʼ"  # Hausa
    "ịỊụỤṅṄ̄"  # Igbo
    "₦’“”–—"  # noqa: RUF001 (naira sign, quotes, en and em dash: intended)
)
RANGES = [
    (0x0020, 0x007E),  # Basic Latin
    (0x00A0, 0x017F),  # Latin-1 Supplement, Latin Extended-A
    (0x0181, 0x0181),
    (0x018A, 0x018A),
    (0x0198, 0x0199),
    (0x01B3, 0x01B4),  # Hausa hooked letters
    (0x01F8, 0x01F9),  # n with grave
    (0x0253, 0x0253),
    (0x0257, 0x0257),  # b and d with hook
    (0x02BC, 0x02BC),  # modifier letter apostrophe (Hausa)
    (0x02C6, 0x02C7),
    (0x02D8, 0x02DD),  # spacing accents
    (0x0300, 0x0304),
    (0x0307, 0x0308),
    (0x030C, 0x030C),
    (0x0323, 0x0323),  # combining marks: tones, macron, dots
    (0x1E00, 0x1EFF),  # Latin Extended Additional (dot below, dot above)
    (0x2010, 0x2027),
    (0x2030, 0x203A),
    (0x2044, 0x2044),  # punctuation
    (0x20A6, 0x20A6),  # naira sign
    (0x20AC, 0x20AC),
    (0x2122, 0x2122),
    (0x2212, 0x2212),
]
FEATURES = ["kern", "mark", "mkmk", "ccmp", "liga", "locl", "tnum", "lnum", "pnum"]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fetch(download: bool) -> None:
    SOURCE_DIR.mkdir(parents=True, exist_ok=True)
    for name, (url, digest) in SOURCES.items():
        path = SOURCE_DIR / name
        if not path.exists():
            if not download:
                sys.exit(f"missing {path}; run with --download")
            with urllib.request.urlopen(url, timeout=60) as response:
                path.write_bytes(response.read())
        if digest and sha256(path) != digest:
            sys.exit(f"{path}: SHA-256 {sha256(path)} is not the pinned {digest}")


def build() -> Path:
    font = instancer.instantiateVariableFont(
        TTFont(SOURCE_DIR / "NotoSans[wdth,wght].ttf"), {"wdth": 100, "wght": (400, 700)}
    )
    with tempfile.TemporaryDirectory() as tmp:
        # Reload the instance eagerly: the subsetter fails on the instancer's lazy tables.
        instance = Path(tmp) / "instance.ttf"
        font.recalcTimestamp = False  # keep the source date: same input, same bytes
        font.save(instance)
        font = TTFont(instance, lazy=False, recalcTimestamp=False)
    options = subset.Options()
    options.layout_features = FEATURES
    options.name_IDs = ["*"]  # type: ignore[assignment]  # fontTools accepts "*"
    options.notdef_outline = True
    subsetter = subset.Subsetter(options)
    subsetter.populate(unicodes=[u for a, b in RANGES for u in range(a, b + 1)])
    subsetter.subset(font)
    cmap = font.getBestCmap() or {}
    missing = [f"U+{ord(c):04X}" for c in REQUIRED if ord(c) not in cmap]
    if missing:
        sys.exit(f"the subset lacks {' '.join(missing)}")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / OUT_NAME
    font.flavor = "woff2"
    font.save(out)
    shutil.copyfile(SOURCE_DIR / "OFL.txt", OUT_DIR / "OFL.txt")
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the Noto Sans subset (D29).")
    parser.add_argument("--download", action="store_true", help="fetch the pinned source font")
    args = parser.parse_args()
    fetch(args.download)
    out = build()
    print(f"wrote {out} ({out.stat().st_size:,} bytes, SHA-256 {sha256(out)})")


if __name__ == "__main__":
    main()
