"""Synthetic public files for the API tests: invented numbers, the real files' shapes."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import duckdb
import pytest
from curbcut_api.app import create_app
from curbcut_api.data import Store, dir_fetcher
from fastapi.testclient import TestClient

# Two real names (to test slugs with spaces), the rest invented; every number is invented.
_FAKE = [f"{a}{b}" for a in "PQ" for b in "ABCDEFGHIJKLMNOPQRS"][:35]
NAMES = ["Akwa Ibom", "Federal Capital Territory", *(f"Fake State {x}" for x in _FAKE)]
CODES = ["NG-AK", "NG-FC", *(f"NG-{x}" for x in _FAKE)]
ZONES = ["Zone One", "Zone Two"]


def _cell(measure: str, age: str, sex: str, estimate: float | None) -> dict[str, Any]:
    return {
        "measure": measure,
        "age_group": age,
        "sex": sex,
        "estimate": estimate,
        "se": 0.01,
        "ci_low": None if estimate is None else estimate - 0.02,
        "ci_high": None if estimate is None else estimate + 0.02,
        "n_unweighted": 500,
        "n_effective": 250.5,
        "df": 40,
        "precision_flag": "reliable",
        "precision_reason": None,
        "suppressed": False,
    }


def state_cells() -> list[dict[str, Any]]:
    rows = []
    for i, (name, code) in enumerate(zip(NAMES, CODES, strict=True)):
        for measure in ("disability3", "seeing_3plus"):
            for age in ("18+", "5-17"):
                for sex in ("all", "female"):
                    cell = _cell(measure, age, sex, 0.01 + i / 1000)
                    rows.append(
                        {
                            "state": name,
                            "state_code": code,
                            "zone": ZONES[i % 2],
                            **cell,
                            "has_data": True,
                            "population_2023": 1_000_000 + i,
                        }
                    )
    # A suppressed cell whose file still holds numbers: the API must not pass them on.
    rows[3].update(suppressed=True, precision_flag="unreliable", precision_reason="n < 30")
    # A cell with no data.
    rows[5].update(has_data=False, estimate=None, ci_low=None, ci_high=None)
    return rows


def national_zone_cells() -> list[dict[str, Any]]:
    rows = []
    for level, geography in (("national", "NG"), ("zone", ZONES[0]), ("zone", ZONES[1])):
        for measure, sexes in (("disability3", ("all", "female")), ("hearing_level_1", ("all",))):
            for sex in sexes:
                rows.append(
                    {
                        "geography_level": level,
                        "geography": geography,
                        **_cell(measure, "18+", sex, 0.05),
                    }
                )
    return rows


def comparison_rows() -> list[dict[str, Any]]:
    base = {
        "ci_low_percent": None,
        "ci_high_percent": None,
        "population": "Invented",
        "definition": "Invented",
        "source": "Invented source",
        "source_url": "https://example.org/",
    }
    return [
        {"figure_id": "b", "sort_order": 2, "label": "B", "kind": "survey", "value_percent": 3.0}
        | base,
        {"figure_id": "a", "sort_order": 1, "label": "A", "kind": "assumed", "value_percent": 15.0}
        | base,
    ]


def states_doc() -> list[dict[str, Any]]:
    return [
        {
            "state": name,
            "state_code": code,
            "zone": ZONES[i % 2],
            "capital": f"Capital {i}",
            "capital_source_url": "https://example.org/",
            "slogan": "Invented",
            "slogan_source_url": "https://example.org/",
            "population_2023": 1_000_000 + i,
            "jonapwd_total": 150_000 + i,
            "share_of_national": 0.027,
            "rank_of_37": i + 1,
            "dhs2024": None,
        }
        for i, (name, code) in enumerate(zip(NAMES, CODES, strict=True))
    ]


def poverty_doc() -> dict[str, Any]:
    return {
        "note": "Invented note.",
        "estimates": {"primary": {"estimate": 0.1, "ci_low": 0.05, "ci_high": 0.15}},
        "summary": {"mpi": {"n": {"value": 100}}},
        "derived": {"verdict": "invented"},
    }


def write_parquet(path: Path, rows: list[dict[str, Any]]) -> None:
    with duckdb.connect() as con:
        con.execute("create table t as select unnest(?, recursive := true)", [rows])
        con.execute(f"copy t to '{path.as_posix()}' (format parquet)")


def write_fixtures(directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    write_parquet(directory / "dhs2024_state_prevalence.parquet", state_cells())
    write_parquet(directory / "dhs2024_national_zone.parquet", national_zone_cells())
    write_parquet(directory / "prevalence_comparison.parquet", comparison_rows())
    (directory / "states.json").write_text(json.dumps(states_doc()), encoding="utf-8")
    (directory / "poverty.json").write_text(json.dumps(poverty_doc()), encoding="utf-8")
    return directory


@pytest.fixture
def fx() -> SimpleNamespace:
    """The fixture builders, for tests that break one file on purpose."""
    return SimpleNamespace(
        write_parquet=write_parquet,
        state_cells=state_cells,
        national_zone_cells=national_zone_cells,
        comparison_rows=comparison_rows,
    )


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    return write_fixtures(tmp_path / "data")


@pytest.fixture
def make_client(data_dir: Path) -> Callable[..., TestClient]:
    def make(env: dict[str, str] | None = None, store: Store | None = None) -> TestClient:
        env = {"CURBCUT_RATE_LIMIT": "1000/minute"} | (env or {})
        store = store or Store(dir_fetcher(data_dir), f"directory {data_dir}")
        return TestClient(create_app(env, store))

    return make


@pytest.fixture
def client(make_client: Callable[..., TestClient]) -> TestClient:
    return make_client()
