"""Build the site's chart documents from the exported Parquet marts.

Run after ``export_marts.py``, from the repo root:
``uv run python packages/transform/scripts/build_charts.py``.

Each chart goes through ``disability_access_charts`` so it carries data-derived alt-text,
a data table and an accessibility audit. The build fails if any audit fails.

* ``prevalence_map``: DHS 2024 DISABILITY3, adults 18+, by state, in fixed classes, as an
  experimental choropleth document (``disability_access_charts.maps``) drawn with the same
  projected paths as the locator map (``build_map.py``);
* ``prevalence_by_state``: the same 37 estimates with their 95% intervals, as a dot plot;
* ``national_by_type`` and ``national_by_state``: JONAPWD's assumed figures, as bars.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import duckdb
from disability_access_charts import Series, bar, dot
from disability_access_charts.maps import choropleth

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DATA = ROOT / "site" / "public" / "data"

SOURCE = "JONAPWD, 2025 Assumptive Disability Disaggregated Data"
DHS_SOURCE = "Nigeria DHS 2024 (NPC and ICF), Curb Cut estimates"

# Fixed, rounded classes for the prevalence map (author, 2026-10-28): under 2%, 2-3%, 3-4%,
# 4-6%, 6% and over. With the DHS 2024 state estimates (0.8% to 11.3%) every class has
# states (12, 11, 4, 6 and 4); the audit warns if one is ever empty.
MAP_BREAKS = (2, 3, 4, 6)

PREVALENCE_LABEL = "Adults with disability (%)"
FLAG_LABELS = {
    "reliable": "Reliable",
    "review": "Review: few events",
    "unreliable": "Unreliable",
}


def _load_build_map() -> ModuleType:
    """build_map.py lives next to this script; load it by path (scripts are not a package)."""
    spec = importlib.util.spec_from_file_location(
        "build_map", Path(__file__).with_name("build_map.py")
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def national_by_type(data_dir: Path) -> dict:
    parquet = (data_dir / "jonapwd_national_by_type.parquet").as_posix()
    rows = duckdb.sql(
        "select disability_type_label, persons "
        f"from read_parquet('{parquet}') order by persons desc, sort_order"
    ).fetchall()
    return bar(
        [str(label) for label, _ in rows],
        [int(persons) for _, persons in rows],
        title="Persons with disabilities by type, all 37 states (JONAPWD estimates)",
        value_label="Persons",
        category_label="Disability type",
        source=SOURCE,
        chart_id="national_by_type",
    )


def national_by_state(data_dir: Path) -> dict:
    parquet = (data_dir / "jonapwd_state_by_type.parquet").as_posix()
    rows = duckdb.sql(
        "select state, any_value(state_total) as total "
        f"from read_parquet('{parquet}') group by state order by total desc, state"
    ).fetchall()
    return bar(
        [str(state) for state, _ in rows],
        [int(total) for _, total in rows],
        title="Persons with disabilities by state, all types (JONAPWD estimates)",
        value_label="Persons",
        category_label="State",
        source=SOURCE,
        chart_id="national_by_state",
    )


def headline_rows(data_dir: Path) -> list[tuple]:
    """DHS 2024 DISABILITY3, adults 18+, both sexes, one row per published state, highest first.

    Values are percentages. States without a published cell (never in the real build) are
    left out of both charts; the page says how many states are shown.
    """
    parquet = (data_dir / "dhs2024_state_prevalence.parquet").as_posix()
    return duckdb.sql(
        "select state, state_code, 100 * estimate, 100 * ci_low, 100 * ci_high, precision_flag "
        f"from read_parquet('{parquet}') "
        "where measure = 'disability3' and age_group = '18+' and sex = 'all' "
        "and has_data and not suppressed "
        "order by estimate desc, state"
    ).fetchall()


def prevalence_by_state(data_dir: Path) -> dict:
    rows = headline_rows(data_dir)
    return dot(
        [str(r[0]) for r in rows],
        [
            Series(
                PREVALENCE_LABEL,
                tuple(float(r[2]) for r in rows),
                tuple(float(r[3]) for r in rows),
                tuple(float(r[4]) for r in rows),
            )
        ],
        title="Disability among adults 18+ by state, with 95% confidence intervals",
        value_label=PREVALENCE_LABEL,
        category_label="State",
        source=DHS_SOURCE,
        unit="percent",
        decimals=1,
        chart_id="prevalence_by_state",
    )


def prevalence_map(data_dir: Path, build_map: ModuleType) -> dict:
    geo = build_map.build(
        json.loads(build_map.DEFAULT_GEOJSON.read_text(encoding="utf-8")), build_map.SEEDS
    )
    rows = headline_rows(data_dir)
    return choropleth(
        [str(r[0]) for r in rows],
        [str(r[1]) for r in rows],
        [float(r[2]) for r in rows],
        lower=[float(r[3]) for r in rows],
        upper=[float(r[4]) for r in rows],
        paths=geo["paths"],
        view_box=geo["viewBox"],
        rings=geo["rings"],
        attribution=geo["attribution"],
        breaks=MAP_BREAKS,
        title="Disability among adults 18+ by state",
        value_label=PREVALENCE_LABEL,
        category_label="State",
        source=DHS_SOURCE,
        unit="percent",
        decimals=1,
        extra_columns=[("Precision", [FLAG_LABELS.get(str(r[5]), str(r[5])) for r in rows])],
        chart_id="prevalence_map",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Build chart JSON documents for the site.")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA)
    args = parser.parse_args()
    out_dir = args.data_dir / "charts"
    out_dir.mkdir(parents=True, exist_ok=True)

    failed = False
    docs = {
        "prevalence_map": prevalence_map(args.data_dir, _load_build_map()),
        "prevalence_by_state": prevalence_by_state(args.data_dir),
        "national_by_type": national_by_type(args.data_dir),
        "national_by_state": national_by_state(args.data_dir),
    }
    for name, doc in docs.items():
        path = out_dir / f"{name}.json"
        path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8", newline="\n")
        status = "passed" if doc["audit"]["passed"] else "FAILED"
        print(f"wrote {path} (audit {status}, {doc['audit']['warnings']} warning(s))")
        failed = failed or not doc["audit"]["passed"]
    if failed:
        print("A chart failed its accessibility audit.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
