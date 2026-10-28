"""GRID3 facility counts: the pure aggregation on invented records, and the committed output.

The GeoPackage is git-ignored, so CI tests the committed 37-row CSV, not the extraction.
"""

from __future__ import annotations

import csv

import pytest
from curbcut_ingest.grid3 import CSV_COLUMNS, OUT, Grid3Error, aggregate, read_population
from curbcut_ingest.states import SEEDS, StateLookup

LOOKUP = StateLookup.from_seeds()
POPULATION = {name: 100_000 for name in LOOKUP.states}


def _one_each() -> list[tuple[str, str, str]]:
    return [(name, "Public", "Primary") for name in LOOKUP.states]


def test_aggregate_counts_and_rate() -> None:
    records = [
        *_one_each(),
        ("Fct", "Private", "Secondary"),  # source spelling, resolved through the alias seed
        ("ABIA", "Unknown", "Tertiary"),
        ("Abia", "Public", "Unknown"),
    ]
    rows = {r["state"]: r for r in aggregate(records, LOOKUP, POPULATION)}
    assert len(rows) == 37
    fct = rows["Federal Capital Territory"]
    assert fct["state_code"] == "NG-FC"
    assert (fct["facilities"], fct["facilities_public"], fct["facilities_secondary_tertiary"]) == (
        2,
        1,
        1,
    )
    abia = rows["Abia"]
    assert (abia["facilities"], abia["facilities_public"], abia["facilities_primary"]) == (3, 2, 1)
    assert abia["facilities_secondary_tertiary"] == 1
    assert abia["facilities_per_100k"] == 3.0


def test_aggregate_rejects_missing_state() -> None:
    records = [r for r in _one_each() if r[0] != "Lagos"]
    with pytest.raises(Grid3Error, match="Lagos"):
        aggregate(records, LOOKUP, POPULATION)


def test_aggregate_rejects_unknown_label() -> None:
    with pytest.raises(Grid3Error, match="Atlantis"):
        aggregate([*_one_each(), ("Atlantis", "Public", "Primary")], LOOKUP, POPULATION)


def test_aggregate_rejects_bad_population() -> None:
    with pytest.raises(Grid3Error, match="population"):
        aggregate(_one_each(), LOOKUP, {**POPULATION, "Kano": 0})


def test_committed_output() -> None:
    with OUT.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    assert list(rows[0]) == CSV_COLUMNS
    assert len(rows) == 37
    assert {r["state_code"] for r in rows} == {s.state_code for s in LOOKUP.states.values()}
    population = read_population(SEEDS)
    for r in rows:
        assert int(r["population_2023"]) == population[r["state"]]
        n = int(r["facilities"])
        assert n > 0
        assert int(r["facilities_public"]) <= n
        assert int(r["facilities_primary"]) + int(r["facilities_secondary_tertiary"]) <= n
        assert float(r["facilities_per_100k"]) == pytest.approx(
            n / int(r["population_2023"]) * 1e5, abs=1e-4
        )
    assert sum(int(r["facilities"]) for r in rows) == 51_022  # GRID3 v2.0 record count (D57)
