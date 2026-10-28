"""FH covariates: pure helpers on invented inputs, and checks on the committed outputs.

The rasters and PDFs are git-ignored, so CI tests the committed CSVs, not the extraction.
"""

from __future__ import annotations

import csv
import math

import numpy as np
import pytest
from curbcut_ingest.covariates import (
    AGES,
    CSV_COLUMNS,
    MPI_TABLE,
    OUT_CSV,
    CovariateError,
    StateShape,
    assemble,
    check_mpi_table,
    polygon_area,
    read_mpi_table,
    read_population,
    zonal_sum,
)
from curbcut_ingest.states import StateLookup

LOOKUP = StateLookup.from_seeds()


def _committed() -> list[dict[str, str]]:
    with OUT_CSV.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


# --- helpers ---------------------------------------------------------------------


def test_polygon_area_subtracts_holes() -> None:
    square = [[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]]
    hole = [[2, 2], [4, 2], [4, 4], [2, 4], [2, 2]]
    assert polygon_area({"type": "Polygon", "coordinates": [square]}) == 100
    assert polygon_area({"type": "Polygon", "coordinates": [square, hole]}) == 96
    multi = {"type": "MultiPolygon", "coordinates": [[square], [hole]]}
    assert polygon_area(multi) == 104


def test_zonal_sum() -> None:
    zones = np.array([[0, 1], [2, 2]], dtype="uint8")
    values = np.array([[5.0, 1.0], [2.0, 3.0]])
    assert zonal_sum(values, zones, 2).tolist() == [5.0, 1.0, 5.0]


def test_assemble_on_invented_sums() -> None:
    shapes = [StateShape(s, LOOKUP.states[s].state_code, {}) for s in sorted(LOOKUP.states)]
    n = len(shapes) + 1
    # Every band holds 100 people per state, except Lagos (zone index of "Lagos").
    wp = {f"{sex}_{a}": np.full(n, 100.0) for sex in ("f", "m") for a in AGES}
    ghs_total, ghs_urban = np.full(n, 1000.0), np.full(n, 250.0)
    mpi = {s.state: {"h_pct": 50.0} for s in shapes}
    population = {s.state: 1_000_000 for s in shapes}
    area = {s.state: 10_000.0 for s in shapes}
    area["Lagos"] = 1_000.0
    rows = assemble(shapes, wp, ghs_total, ghs_urban, mpi, population, area)
    first = rows[0]
    assert first["c1_share_60plus"] == round(10 / 36, 6)
    assert first["c2_urban_share"] == 0.25
    assert first["c3_mpi_headcount"] == 0.5
    assert first["c5_log_density"] == round(math.log(100), 6)
    assert first["wp2020_pop_total"] == 3600
    assert first["wp2020_pop_18plus"] == 2 * (13 * 100 + 40)
    area["Lagos"] = 10_000.0
    area["Kano"] = 500.0
    with pytest.raises(CovariateError, match="densest"):
        assemble(shapes, wp, ghs_total, ghs_urban, mpi, population, area)


def test_check_mpi_table_rejects_a_swapped_value() -> None:
    table = read_mpi_table(MPI_TABLE, LOOKUP)
    broken = {s: dict(r) for s, r in table.items()}
    broken["Kano"]["h_pct"], broken["Kebbi"]["h_pct"] = (
        broken["Kebbi"]["h_pct"],
        broken["Kano"]["h_pct"],
    )
    with pytest.raises(CovariateError):
        check_mpi_table(broken, set(LOOKUP.states))


# --- committed outputs ---------------------------------------------------------------


def test_mpi_transcription_passes_its_checks() -> None:
    table = read_mpi_table(MPI_TABLE, LOOKUP)
    assert len(table) == 37
    assert table["Ondo"]["h_pct"] == 27.2
    assert table["Sokoto"]["h_pct"] == 90.5


def test_covariates_shape_and_ranges() -> None:
    rows = _committed()
    assert len(rows) == 37
    assert list(rows[0]) == CSV_COLUMNS
    assert {r["state"] for r in rows} == set(LOOKUP.states)
    for r in rows:
        assert all(v != "" for v in r.values()), r["state"]
        assert LOOKUP.states[r["state"]].state_code == r["state_code"]
        for col in ("c1_share_60plus", "c2_urban_share", "c3_mpi_headcount"):
            assert 0 <= float(r[col]) <= 1, (r["state"], col)
        # 60+ is about 4-6% nationally; no state should be far outside 2-10%.
        assert 0.02 < float(r["c1_share_60plus"]) < 0.10, r["state"]
        assert 0 < int(r["wp2020_pop_18plus"]) < int(r["wp2020_pop_total"])


def test_covariates_national_share_60plus() -> None:
    rows = _committed()
    total = sum(int(r["wp2020_pop_total"]) for r in rows)
    aged = sum(float(r["c1_share_60plus"]) * int(r["wp2020_pop_total"]) for r in rows)
    assert 0.03 < aged / total < 0.07


def test_covariates_density_order() -> None:
    rows = sorted(_committed(), key=lambda r: float(r["c5_log_density"]), reverse=True)
    assert rows[0]["state"] == "Lagos"
    population = read_population()
    for r in rows:
        assert int(r["population_2023"]) == population[r["state"]]
        expected = math.log(int(r["population_2023"]) / float(r["area_km2"]))
        assert float(r["c5_log_density"]) == pytest.approx(expected, abs=1e-4)


def test_covariates_mpi_matches_transcription() -> None:
    table = read_mpi_table(MPI_TABLE, LOOKUP)
    for r in _committed():
        assert float(r["c3_mpi_headcount"]) == pytest.approx(table[r["state"]]["h_pct"] / 100)
