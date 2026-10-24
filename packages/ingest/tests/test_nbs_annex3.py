"""Annex 3 parser on an invented sheet (the real datasheet is git-ignored)."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest
from curbcut_ingest.nbs_annex3 import Annex3Error, parse_rows, write_seed
from curbcut_ingest.states import StateLookup

LOOKUP = StateLookup.from_seeds()


def _sheet(*, break_row: str | None = None) -> list[tuple]:
    rows: list[tuple] = [
        (None,),
        ("Annex 3 : Projected Population, 2023",),
        ("State", "Males", "Females", "Total"),
    ]
    m_sum = f_sum = 0
    for i, state in enumerate(sorted(LOOKUP.states)):
        label = f"{state} state" if i % 3 == 0 else state.upper()
        if state == "Federal Capital Territory":
            label = "FCT Abuja"
        m, f = 1000 + i, 900 + i
        t = m + f + (1 if state == break_row else 0)
        rows.append((label, m, f, t))
        m_sum, f_sum = m_sum + m, f_sum + f
    rows.append(("Nigeria", m_sum, f_sum, m_sum + f_sum))
    rows.append(("Source: National Population Commission", None, None, None))
    return rows


def test_parse_rows() -> None:
    states, nigeria = parse_rows(_sheet(), LOOKUP)
    assert len(states) == 37
    assert states["Abia"] == (1000, 900, 1900)
    assert nigeria[2] == sum(v[2] for v in states.values())


def test_parse_rows_rejects_bad_totals() -> None:
    with pytest.raises(Annex3Error):
        parse_rows(_sheet(break_row="Kano"), LOOKUP)
    with pytest.raises(Annex3Error):
        parse_rows(_sheet()[:10], LOOKUP)


def test_write_seed(tmp_path: Path) -> None:
    states, _ = parse_rows(_sheet(), LOOKUP)
    path = tmp_path / "seed.csv"
    write_seed(states, path)
    rows = list(csv.DictReader(path.open(encoding="utf-8")))
    assert len(rows) == 74
    assert rows[0] == {"state": "Abia", "sex": "male", "population_2023": "1000"}
