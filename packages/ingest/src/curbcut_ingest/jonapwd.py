"""Extract the per-state disability-type figures from the JONAPWD 2025 PDF.

Source: JONAPWD, "2025 Assumptive Disability Disaggregated Data" (c) JONAPWD, all rights
reserved. The PDF is never committed or redistributed; only the figures are cited.

Pages 14-50 are Power BI exports, one per state (36 states + FCT). Each page draws ten
bars sorted by value, either vertically or horizontally. The text layer gives the state
name, the ten value labels and the ten category labels, but text order alone does not
say which value belongs to which category. This module maps them by geometry instead:

* each value label sits at the end of its bar, and its category label is printed beside
  the bar's base, so all three share a centre on the axis the bars are spread along;
* bar lengths must be proportional to the values (the axis starts at zero), which is
  checked as an independent consistency test on every page.

The parser works on plain word and rectangle dicts so it can be tested without the PDF.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import re
import statistics
import sys
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SOURCE_URL = "https://jonapwdng.org/wp-content/uploads/2026/03/2025-Assumptive-Disability-Disaggregated-Data-2.pdf"
PUBLISHER_URL = "https://jonapwdng.org/10865-2/"
EXPECTED_SHA256 = "c861f33cdfd8ed79e83598acb853dc2295667b9d169cd511e4beb1a54d638732"
STATE_PAGES = range(14, 51)
TOTALS_PAGE = 10

# Canonical order follows the national donut legend (PDF page 11).
DISABILITY_TYPES: dict[str, str] = {
    "PERSONS WITH PHYSICAL DISABILITIES": "physical",
    "PERSONS WITH HEARING IMPAIRMENT": "hearing",
    "PERSONS WITH VISUAL IMPAIRMENT": "visual",
    "PERSONS AFFECTED BY LEPROSY": "leprosy",
    "PERSONS WITH ALBINISM": "albinism",
    "PERSONS WITH SPINAL CORD INJURY": "spinal_cord_injury",
    "PERSONS WITH INTELLECTUAL DISABILITIES": "intellectual",
    "OTHERS": "others",
    "PERSONS WITH DEAF-BLINDNESS": "deaf_blindness",
    "PERSONS WITH LITTLE STATURE": "little_stature",
}

CSV_COLUMNS = ["state", "disability_type", "disability_type_label", "persons", "source_page"]

Box = Mapping[str, Any]

_NUMBER = re.compile(r"^\d[\d,]*$")
# Power BI truncates labels that do not fit with an ellipsis (U+2026), e.g.
# "PERSONS WITH HEARI..." or "DEAF-BLINDN...". The text before it is resolved to a
# category by unique prefix.
_ELLIPSIS = "…"

TITLE_MIN_HEIGHT = 20.0
"""State names are set in a large font (about 40pt); everything else is about 9-10pt."""
LABEL_TOLERANCE = 30.0
"""Maximum distance (pt) between a label word's centre and its value's centre."""
BAR_TOLERANCE = 5.0
"""Maximum distance (pt) between a value's centre and its bar's centre."""
VALUE_GAP = 20.0
"""Maximum gap (pt) between the end of a bar and its value label.

Power BI prints the label just beyond the bar end, or just inside it when there is no room
(the longest bar on some horizontal pages)."""
PROPORTION_TOLERANCE = 0.02
"""Relative tolerance for the values-proportional-to-bar-length check."""
PROPORTION_MIN_LENGTH = 10.0
"""Bars shorter than this (pt) are too small for a meaningful proportion check."""


class ExtractionError(ValueError):
    """The page does not have the expected structure; nothing should be written."""


@dataclass(frozen=True)
class Row:
    state: str
    disability_type: str
    disability_type_label: str
    persons: int
    source_page: int


def _f(box: Box, key: str) -> float:
    return float(box[key])


def _xc(box: Box) -> float:
    return (_f(box, "x0") + _f(box, "x1")) / 2


def _yc(box: Box) -> float:
    return (_f(box, "top") + _f(box, "bottom")) / 2


def resolve_label(text: str) -> str:
    """Map printed (possibly truncated) label text to its canonical category label."""
    truncated = _ELLIPSIS in text
    text = " ".join(text.split(_ELLIPSIS)[0].split()).upper()
    if text in DISABILITY_TYPES:
        return text
    if truncated and text:
        candidates = [label for label in DISABILITY_TYPES if label.startswith(text)]
        if len(candidates) == 1:
            return candidates[0]
    raise ExtractionError(f"cannot resolve category label {text!r}")


@dataclass(frozen=True)
class _Layout:
    """How to read one chart orientation. The 'cross' axis is the one bars are spread along."""

    name: str
    shape: Callable[[Box], bool]  # is this rectangle bar-shaped?
    base_edge: str  # edge all bars share
    cross: Callable[[Box], float]  # centre of a box on the cross axis
    length: Callable[[Box], float]  # bar length
    gap: Callable[[Box, Box], float]  # gap from the bar's end out to its value label
    inset: Callable[[Box, Box], float]  # gap from a label inside the bar to the bar's end
    is_value_side: Callable[[Box, float], bool]  # word lies on the values' side of the base
    is_label_side: Callable[[Box, float], bool]  # word lies on the labels' side of the base


VERTICAL = _Layout(
    "vertical",
    shape=lambda r: 20 <= _f(r, "x1") - _f(r, "x0") <= 120,
    base_edge="bottom",
    cross=_xc,
    length=lambda b: _f(b, "bottom") - _f(b, "top"),
    gap=lambda bar, value: _f(bar, "top") - _f(value, "bottom"),
    inset=lambda bar, value: _f(value, "top") - _f(bar, "top"),
    is_value_side=lambda w, base: _f(w, "bottom") <= base,
    is_label_side=lambda w, base: _f(w, "top") >= base,
)
HORIZONTAL = _Layout(
    "horizontal",
    shape=lambda r: 20 <= _f(r, "bottom") - _f(r, "top") <= 40,
    base_edge="x0",
    cross=_yc,
    length=lambda b: _f(b, "x1") - _f(b, "x0"),
    gap=lambda bar, value: _f(value, "x0") - _f(bar, "x1"),
    inset=lambda bar, value: _f(bar, "x1") - _f(value, "x1"),
    is_value_side=lambda w, base: _f(w, "x0") >= base,
    is_label_side=lambda w, base: _f(w, "x1") <= base,
)


def find_bars(rects: Sequence[Box], expected: int) -> tuple[_Layout, list[Box], float]:
    """Find the chart's bars: exactly ``expected`` bar-shaped rectangles sharing a base edge.

    Vertical bars share a bottom edge; horizontal bars share a left edge.
    """
    for layout in (VERTICAL, HORIZONTAL):
        candidates = [r for r in rects if layout.shape(r)]
        if not candidates:
            continue
        base = statistics.mode(round(_f(r, layout.base_edge), 1) for r in candidates)
        bars = [r for r in candidates if abs(_f(r, layout.base_edge) - base) <= 1.0]
        if len(bars) == expected:
            return layout, bars, base
    raise ExtractionError(f"no set of {expected} bars sharing a base edge")


def parse_state_page(words: Sequence[Box], rects: Sequence[Box], page_number: int) -> list[Row]:
    """Parse one Power BI state page into ten rows, validating the geometry.

    ``words`` need ``text``, ``x0``, ``x1``, ``top`` and ``bottom`` (as produced by
    ``pdfplumber.Page.extract_words``); ``rects`` need the same four coordinates.
    Raises :class:`ExtractionError` if anything about the page is unexpected.
    """
    expected = len(DISABILITY_TYPES)

    def fail(message: str) -> ExtractionError:
        return ExtractionError(f"page {page_number}: {message}")

    try:
        layout, bars, base = find_bars(rects, expected)
    except ExtractionError as exc:
        raise fail(str(exc)) from exc

    title = [w for w in words if _f(w, "bottom") - _f(w, "top") >= TITLE_MIN_HEIGHT]
    if not title:
        raise fail("no state title found")
    state = " ".join(str(w["text"]).strip() for w in sorted(title, key=lambda w: _f(w, "x0")))
    title_bottom = max(_f(w, "bottom") for w in title)
    body = [w for w in words if _f(w, "top") > title_bottom]

    values = [
        w for w in body if _NUMBER.match(str(w["text"]).strip()) and layout.is_value_side(w, base)
    ]
    labels = [w for w in body if layout.is_label_side(w, base)]
    if len(values) != expected:
        raise fail(f"expected {expected} values, got {len(values)}")

    groups: dict[int, list[Box]] = {i: [] for i in range(len(values))}
    for word in labels:
        distances = [abs(layout.cross(word) - layout.cross(v)) for v in values]
        nearest = min(range(len(values)), key=distances.__getitem__)
        if distances[nearest] > LABEL_TOLERANCE:
            raise fail(f"label word {word['text']!r} does not line up with a value")
        groups[nearest].append(word)

    rows: list[Row] = []
    ratios: list[float] = []
    for i, value_word in enumerate(values):
        persons = int(str(value_word["text"]).replace(",", ""))
        ordered = sorted(groups[i], key=lambda w: (_f(w, "top"), _f(w, "x0")))
        try:
            label = resolve_label(" ".join(str(w["text"]) for w in ordered))
        except ExtractionError as exc:
            raise fail(str(exc)) from exc

        matching = [
            b for b in bars if abs(layout.cross(b) - layout.cross(value_word)) <= BAR_TOLERANCE
        ]
        if len(matching) != 1:
            raise fail(f"value {persons} lines up with {len(matching)} bars")
        bar = matching[0]
        outside = 0 <= layout.gap(bar, value_word) <= VALUE_GAP
        inside = 0 <= layout.inset(bar, value_word) <= VALUE_GAP
        if not (outside or inside):
            raise fail(f"value {persons} is not at the end of its bar")
        length = layout.length(bar)
        if length >= PROPORTION_MIN_LENGTH:
            ratios.append(persons / length)

        rows.append(Row(state, DISABILITY_TYPES[label], label, persons, page_number))

    if len({r.disability_type for r in rows}) != expected:
        raise fail("a category appears twice")
    if len(ratios) < 3:
        raise fail("too few bars to check proportions")
    mid = statistics.median(ratios)
    if any(abs(r - mid) / mid > PROPORTION_TOLERANCE for r in ratios):
        raise fail("values are not proportional to bar lengths")

    order = list(DISABILITY_TYPES.values())
    return sorted(rows, key=lambda r: order.index(r.disability_type))


def parse_totals_page(words: Sequence[Box]) -> tuple[dict[str, int], int | None]:
    """Parse the scrolled 'STATES / Sum of TOTAL POPULATION' table on PDF page 10.

    Returns the state rows visible on the page (the table is cut off after PLATEAU)
    and the printed grand total.
    """
    names = [
        w
        for w in words
        if _f(w, "x0") < 40 and re.match(r"^[A-Za-z][A-Za-z -]*$", str(w["text"]).strip())
    ]
    numbers = [w for w in words if 240 < _f(w, "x0") < 300 and _NUMBER.match(str(w["text"]))]
    totals: dict[str, int] = {}
    grand: int | None = None
    for name in names:
        same_line = [n for n in numbers if abs(_f(n, "top") - _f(name, "top")) < 1.0]
        if len(same_line) != 1:
            continue
        value = int(str(same_line[0]["text"]).replace(",", ""))
        label = str(name["text"]).strip()
        if label.upper() == "TOTAL":
            grand = value
        else:
            totals[label] = value
    return totals, grand


def canonical_key(name: str) -> str:
    """Letters only, upper case: 'Cross-River' and 'CROSS RIVER' compare equal."""
    return re.sub(r"[^A-Z]", "", name.upper())


def cross_check(
    rows: Sequence[Row], page_totals: Mapping[str, int], grand: int | None
) -> dict[str, Any]:
    """Compare per-state sums of the ten types with the totals printed on page 10."""
    by_state: dict[str, int] = {}
    by_type: dict[str, int] = {}
    for row in rows:
        by_state[row.state] = by_state.get(row.state, 0) + row.persons
        by_type[row.disability_type] = by_type.get(row.disability_type, 0) + row.persons
    lookup = {canonical_key(s): total for s, total in by_state.items()}
    if "FEDERALCAPITALTERRITORY" in lookup:
        lookup["FCT"] = lookup["FEDERALCAPITALTERRITORY"]
    compared = [
        {"state": name, "printed": printed, "sum_of_types": lookup.get(canonical_key(name))}
        for name, printed in page_totals.items()
    ]
    return {
        "page_10_states_visible": len(page_totals),
        "page_10_mismatches": [c for c in compared if c["printed"] != c["sum_of_types"]],
        "page_10_grand_total": grand,
        "sum_of_all_rows": sum(r.persons for r in rows),
        "national_by_type": by_type,
    }


def write_csv(rows: Iterable[Row], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh, lineterminator="\n")
        writer.writerow(CSV_COLUMNS)
        for r in rows:
            writer.writerow(
                [r.state, r.disability_type, r.disability_type_label, r.persons, r.source_page]
            )


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def extract(pdf_path: Path) -> tuple[list[Row], dict[str, Any]]:
    import pdfplumber  # imported here so the pure parser and its tests do not need it

    rows: list[Row] = []
    with pdfplumber.open(pdf_path) as pdf:
        for number in STATE_PAGES:
            page = pdf.pages[number - 1]
            words = page.extract_words(keep_blank_chars=True)
            rows.extend(parse_state_page(words, page.rects, number))
        totals_words = pdf.pages[TOTALS_PAGE - 1].extract_words(keep_blank_chars=True)
    states = {r.state for r in rows}
    if len(states) != len(STATE_PAGES):
        raise ExtractionError(f"expected {len(STATE_PAGES)} distinct states, got {len(states)}")
    totals, grand = parse_totals_page(totals_words)
    return rows, cross_check(rows, totals, grand)


def render_pages(pdf_path: Path, pages: Iterable[int], out_dir: Path, scale: int = 2) -> None:
    """Render pages to PNG for hand validation. Keep the output out of git."""
    import pypdfium2 as pdfium

    out_dir.mkdir(parents=True, exist_ok=True)
    doc = pdfium.PdfDocument(str(pdf_path))
    try:
        for number in pages:
            doc[number - 1].render(scale=scale).to_pil().save(out_dir / f"page-{number:02d}.png")
    finally:
        doc.close()


def _page_list(spec: str) -> list[int]:
    pages: list[int] = []
    for part in spec.split(","):
        lo, _, hi = part.partition("-")
        pages.extend(range(int(lo), int(hi or lo) + 1))
    return pages


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Extract JONAPWD 2025 per-state disability-type figures to CSV."
    )
    parser.add_argument("pdf", type=Path, help="path to the JONAPWD 2025 PDF (git-ignored)")
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("data/public/jonapwd"),
        help="directory for state_disability_type.csv and manifest.json",
    )
    parser.add_argument("--render", type=Path, help="also render pages to PNG here (not in git)")
    parser.add_argument("--pages", default="10,11,14-50", help="pages to render, e.g. 10,14-20")
    args = parser.parse_args(argv)

    digest = sha256(args.pdf)
    if digest != EXPECTED_SHA256:
        print(f"PDF SHA-256 {digest} is not the validated {EXPECTED_SHA256}", file=sys.stderr)
        return 1
    rows, checks = extract(args.pdf)
    csv_path = args.out_dir / "state_disability_type.csv"
    write_csv(rows, csv_path)
    manifest = {
        "source": "JONAPWD, 2025 Assumptive Disability Disaggregated Data",
        "copyright": "(c) JONAPWD. All rights reserved. Figures cited; PDF not redistributed.",
        "source_url": SOURCE_URL,
        "publisher_page": PUBLISHER_URL,
        "pdf_sha256": digest,
        "pages": f"{STATE_PAGES.start}-{STATE_PAGES.stop - 1}",
        "extracted_on": dt.date.today().isoformat(),
        "method": "pdfplumber text layer; label-to-value mapping by bar geometry",
        "rows": len(rows),
        "cross_check": checks,
    }
    manifest_path = args.out_dir / "manifest.json"
    text = json.dumps(manifest, indent=2) + "\n"
    manifest_path.write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {len(rows)} rows to {csv_path}")
    print(json.dumps(checks, indent=2))

    if args.render:
        pages = _page_list(args.pages)
        render_pages(args.pdf, pages, args.render)
        print(f"rendered {len(pages)} pages to {args.render}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
