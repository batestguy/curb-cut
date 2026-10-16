"""Tests for the JONAPWD page parser, on synthetic geometry (the PDF is never in git)."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest
from curbcut_ingest.jonapwd import (
    DISABILITY_TYPES,
    ExtractionError,
    Row,
    cross_check,
    parse_state_page,
    parse_totals_page,
    resolve_label,
    write_csv,
)

LABELS = list(DISABILITY_TYPES)
# Deliberately not in canonical order, with a tie, as on the real pages.
VALUES = [5000, 4000, 3000, 900, 1200, 1200, 800, 400, 20, 10]
SCALE = 15.0  # persons per point of bar length (tallest bar ~333pt, below the title)
TITLE = {"text": "TEST STATE", "x0": 400.0, "x1": 600.0, "top": 51.0, "bottom": 91.0}


def _vertical_page(
    values: list[int], labels: list[str], *, inside: int | None = None
) -> tuple[list[dict], list[dict]]:
    """Bars spread left to right; values above, labels below the baseline at y=470."""
    words, rects = [TITLE], []
    for i, (value, label) in enumerate(zip(values, labels, strict=True)):
        x0, x1 = 90.0 + i * 84, 156.0 + i * 84
        top = 470.0 - value / SCALE
        rects.append({"x0": x0, "x1": x1, "top": top, "bottom": 470.0})
        mid = (x0 + x1) / 2
        v_top = top + 2 if i == inside else top - 12
        words.append(
            {"text": str(value), "x0": mid - 12, "x1": mid + 12, "top": v_top, "bottom": v_top + 9}
        )
        # Split long labels over lines, like Power BI's word wrap.
        for line, text in enumerate(label.split(" ", 2)):
            y = 480.0 + line * 11
            words.append({"text": text, "x0": mid - 30, "x1": mid + 30, "top": y, "bottom": y + 10})
    # Page furniture that must be ignored: a full-width frame.
    rects.append({"x0": 18.0, "x1": 978.0, "top": 18.0, "bottom": 558.0})
    return words, rects


def _horizontal_page(values: list[int], labels: list[str]) -> tuple[list[dict], list[dict]]:
    """Bars spread top to bottom from x=190; labels left, values right of each bar."""
    words, rects = [TITLE], []
    for i, (value, label) in enumerate(zip(values, labels, strict=True)):
        top, bottom = 122.0 + i * 38.5, 152.0 + i * 38.5
        x1 = 190.0 + value / SCALE
        rects.append({"x0": 190.0, "x1": x1, "top": top, "bottom": bottom})
        mid = (top + bottom) / 2
        words.append(
            {"text": str(value), "x0": x1 + 6, "x1": x1 + 30, "top": mid - 4.5, "bottom": mid + 4.5}
        )
        printed = label if len(label) <= 21 else label[:19] + "…"
        words.append({"text": printed, "x0": 57.0, "x1": 183.0, "top": mid - 5, "bottom": mid + 5})
    rects.append({"x0": 18.0, "x1": 978.0, "top": 18.0, "bottom": 43.5})  # header band
    return words, rects


def _as_dict(rows: list[Row]) -> dict[str, int]:
    return {r.disability_type: r.persons for r in rows}


EXPECTED = {DISABILITY_TYPES[lab]: v for lab, v in zip(LABELS, VALUES, strict=True)}


def test_vertical_page_maps_values_by_geometry() -> None:
    words, rects = _vertical_page(VALUES, LABELS)
    rows = parse_state_page(words, rects, page_number=14)
    assert len(rows) == 10
    assert {r.state for r in rows} == {"TEST STATE"}
    assert _as_dict(rows) == {
        DISABILITY_TYPES[lab]: v for lab, v in zip(LABELS, VALUES, strict=True)
    }
    assert [r.disability_type for r in rows] == list(DISABILITY_TYPES.values())
    assert all(r.source_page == 14 for r in rows)


def test_text_order_does_not_decide_the_mapping() -> None:
    """Shuffling the word list must not change the result."""
    words, rects = _vertical_page(VALUES, LABELS)
    shuffled = [words[0], *reversed(words[1:])]
    assert _as_dict(parse_state_page(shuffled, rects, 1)) == _as_dict(
        parse_state_page(words, rects, 1)
    )


def test_horizontal_page_with_truncated_labels() -> None:
    words, rects = _horizontal_page(VALUES, LABELS)
    rows = parse_state_page(words, rects, page_number=19)
    assert _as_dict(rows) == {
        DISABILITY_TYPES[lab]: v for lab, v in zip(LABELS, VALUES, strict=True)
    }
    # Labels are stored in full even though the page truncated them.
    assert {r.disability_type_label for r in rows} == set(LABELS)


def test_value_printed_inside_the_longest_bar() -> None:
    words, rects = _vertical_page(VALUES, LABELS, inside=0)
    assert _as_dict(parse_state_page(words, rects, 1))["physical"] == 5000


def test_rejects_values_not_proportional_to_bars() -> None:
    words, rects = _vertical_page(VALUES, LABELS)
    # Swap two printed values: the bars no longer match the numbers above them.
    a = next(w for w in words if w["text"] == "5000")
    b = next(w for w in words if w["text"] == "3000")
    a["text"], b["text"] = "3000", "5000"
    with pytest.raises(ExtractionError, match="proportional"):
        parse_state_page(words, rects, 7)


def test_rejects_missing_value() -> None:
    words, rects = _vertical_page(VALUES, LABELS)
    words = [w for w in words if w["text"] != "400"]
    with pytest.raises(ExtractionError, match="expected 10 values"):
        parse_state_page(words, rects, 7)


def test_rejects_unknown_label() -> None:
    labels = [*LABELS[:-1], "PERSONS WITH SOMETHING ELSE"]
    words, rects = _vertical_page(VALUES, labels)
    with pytest.raises(ExtractionError, match="cannot resolve"):
        parse_state_page(words, rects, 7)


def test_rejects_page_without_bars() -> None:
    words, _ = _vertical_page(VALUES, LABELS)
    with pytest.raises(ExtractionError, match="page 3: no set of 10 bars"):
        parse_state_page(words, [], 3)


@pytest.mark.parametrize(
    ("printed", "expected"),
    [
        ("OTHERS", "OTHERS"),
        ("PERSONS WITH DEAF-BLINDN…", "PERSONS WITH DEAF-BLINDNESS"),
        ("PERSONS WITH DEAF-B…", "PERSONS WITH DEAF-BLINDNESS"),
        ("PERSONS AFFECTED B…", "PERSONS AFFECTED BY LEPROSY"),
        ("persons  with\nalbinism", "PERSONS WITH ALBINISM"),
    ],
)
def test_resolve_label(printed: str, expected: str) -> None:
    assert resolve_label(printed) == expected


@pytest.mark.parametrize("printed", ["PERSONS WITH …", "PERSONS WITH", "PERSONS WITH HEARI"])
def test_resolve_label_rejects_ambiguous_or_untruncated_prefixes(printed: str) -> None:
    with pytest.raises(ExtractionError):
        resolve_label(printed)


def test_totals_page_and_cross_check() -> None:
    def word(text: str, x0: float, top: float) -> dict:
        return {"text": text, "x0": x0, "x1": x0 + 30, "top": top, "bottom": top + 10}

    words = [
        word("STATES", 26, 25),
        word("CROSS-RIVER", 26, 47),
        word("150", 264, 47),
        word("FCT", 26, 63),
        word("99", 264, 63),
        word("Total", 26, 543),
        word("250", 253, 543),
    ]
    totals, grand = parse_totals_page(words)
    assert totals == {"CROSS-RIVER": 150, "FCT": 99}
    assert grand == 250
    rows = [
        Row("CROSS RIVER", "physical", "x", 100, 22),
        Row("CROSS RIVER", "hearing", "x", 50, 22),
        Row("FEDERAL CAPITAL TERRITORY", "physical", "x", 100, 28),
    ]
    checks = cross_check(rows, totals, grand)
    assert checks["page_10_mismatches"] == [{"state": "FCT", "printed": 99, "sum_of_types": 100}]
    assert checks["sum_of_all_rows"] == 250
    assert checks["national_by_type"] == {"physical": 200, "hearing": 50}


def test_write_csv(tmp_path: Path) -> None:
    path = tmp_path / "out" / "rows.csv"
    write_csv([Row("ABIA", "physical", "PERSONS WITH PHYSICAL DISABILITIES", 1, 14)], path)
    with path.open(encoding="utf-8") as fh:
        assert list(csv.reader(fh)) == [
            ["state", "disability_type", "disability_type_label", "persons", "source_page"],
            ["ABIA", "physical", "PERSONS WITH PHYSICAL DISABILITIES", "1", "14"],
        ]
