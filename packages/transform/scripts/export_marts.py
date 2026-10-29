"""Export the public dbt marts from DuckDB to Parquet and JSON for the static site.

Run after ``dbt build``, from the repo root:
``uv run python packages/transform/scripts/export_marts.py``.

Opens the warehouse read-only, so it never competes with a dbt writer. Outputs are build
artefacts (git-ignored) under ``site/public/data/``, which Vite copies into the site:

* Parquet: the JONAPWD marts, the DHS 2024 state and national/zone prevalence cells, the
  spatial results by state and by measure, and the comparison;
* ``states.json``: the picker's states, the state card's facts and each state's DHS 2024
  headline (DISABILITY3, adults 18+, both sexes);
* ``prevalence.json``: the national headline and the comparison rows;
* ``spatial.json``: the plain-English spatial sentences from
  ``data/public/spatial/summary.json``, with cluster members named and sorted by name.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import duckdb

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DB = ROOT / "data" / "curbcut.duckdb"
DEFAULT_OUT = ROOT / "site" / "public" / "data"
SPATIAL_SUMMARY = ROOT / "data" / "public" / "spatial" / "summary.json"

# Only public, aggregate marts belong here. Parquet file name -> relation in the warehouse.
EXPORTS = {
    "jonapwd_state_by_type.parquet": "mart_jonapwd_state_by_type",
    "jonapwd_national_by_type.parquet": "mart_jonapwd_national_by_type",
    "spatial_state.parquet": "mart_spatial_state",
    "spatial_moran.parquet": "mart_spatial_moran",
    "prevalence_comparison.parquet": "mart_prevalence_comparison",
}

# DHS 2024 survey cells (disclosure-gated aggregates): Parquet file -> query. Suppressed
# cells keep null numbers. State cells are both sexes and each sex, ages 18+ and 5-17,
# DISABILITY3 and the six domains, with no extra breakdown.
CELL_COLUMNS = (
    "measure, age_group, sex, estimate, se, ci_low, ci_high, n_unweighted, n_effective, df, "
    "precision_flag, precision_reason, suppressed"
)
QUERIES = {
    "dhs2024_state_prevalence.parquet": (
        f"select state, state_code, zone, {CELL_COLUMNS}, has_data, population_2023 "
        "from mart_prevalence_state where source = 'dhs2024' "
        "order by measure, age_group, sex, state"
    ),
    "dhs2024_national_zone.parquet": (
        f"select geography_level, geography, {CELL_COLUMNS} "
        "from mart_prevalence_national_zone where source = 'dhs2024' "
        "order by geography_level, geography, measure, age_group, sex"
    ),
}

# The headline cell: DISABILITY3, adults 18+, both sexes.
HEADLINE = "measure = 'disability3' and age_group = '18+' and sex = 'all'"
HEADLINE_COLUMNS = "estimate, se, ci_low, ci_high, n_unweighted, precision_flag, precision_reason"

DHS_CITATION = (
    "The DHS Program, Nigeria Demographic and Health Survey 2024 (National Population "
    "Commission and ICF); Curb Cut estimates from the microdata, disclosure-checked"
)


def _rows(con: duckdb.DuckDBPyConnection, sql: str) -> list[dict[str, Any]]:
    cursor = con.execute(sql)
    columns = [d[0] for d in cursor.description]
    return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]


def states_payload(con: duckdb.DuckDBPyConnection) -> list[dict[str, Any]]:
    """The state list for the picker, the card's facts and each state's DHS 2024 headline.

    ``dhs2024`` is null where the state has no published headline cell (never in the real
    build; the fixture build leaves one state out on purpose).
    """
    payload = _rows(
        con,
        "select state, state_code, zone, capital, capital_source_url, slogan, "
        "slogan_source_url, population_2023, jonapwd_total, share_of_national, rank_of_37 "
        "from mart_state_profile order by state",
    )
    cells = _rows(
        con,
        f"select state_code, has_data, suppressed, {HEADLINE_COLUMNS} "
        f"from mart_prevalence_state where source = 'dhs2024' and {HEADLINE}",
    )
    headline = {cell.pop("state_code"): cell for cell in cells}
    for state in payload:
        cell = headline.get(state["state_code"])
        if cell is not None and cell.pop("has_data") and not cell.pop("suppressed"):
            state["dhs2024"] = cell
        else:
            state["dhs2024"] = None
    return payload


def prevalence_payload(con: duckdb.DuckDBPyConnection) -> dict[str, Any]:
    """The national headline figure and the comparison rows, for the main page."""
    national = _rows(
        con,
        f"select {HEADLINE_COLUMNS} from mart_prevalence_national_zone "
        f"where source = 'dhs2024' and geography_level = 'national' and {HEADLINE} "
        "and not suppressed",
    )
    if len(national) != 1:
        raise ValueError(f"expected one national headline cell, found {len(national)}")
    return {
        "measure": "disability3",
        "age_group": "18+",
        "source": DHS_CITATION,
        "national": national[0],
        "comparison": _rows(con, "select * from mart_prevalence_comparison order by sort_order"),
    }


def spatial_payload(con: duckdb.DuckDBPyConnection, summary: dict[str, Any]) -> dict[str, Any]:
    """The spatial sentences from summary.json, used as written (P4a step 3).

    Cluster members and LISA states get their names and are sorted by name.
    """
    names = dict(con.execute("select state_code, state from dim_states").fetchall())
    labels = {
        (measure, age): label
        for measure, age, label in con.execute(
            "select measure, age_group, measure_label from mart_spatial_moran"
        ).fetchall()
    }
    keep = ("measure", "age_group", "role", "moran_i", "p_perm", "p_bh", "n_imprecise")
    moran = [
        {
            **{k: r[k] for k in keep},
            "label": labels[(r["measure"], r["age_group"])],
            "sentence": r["sentence"],
        }
        for r in summary["moran"]["results"]
    ]
    groups = [
        {
            "cluster": g["cluster"],
            "n_states": g["n_states"],
            "states": sorted(names[code] for code in g["states"]),
        }
        for g in summary["clusters"]["profiles"]
    ]
    services = summary["services"]
    return {
        "note": summary["note"],
        "moran": moran,
        "lisa": {
            "classes": summary["lisa"]["classes"],
            "significant_states": sorted(
                names[code] for code in summary["lisa"]["significant_states"]
            ),
            "sentence": summary["lisa"]["sentence"],
        },
        "clusters": {
            "k": summary["clusters"]["k"],
            "groups": groups,
            "sentence": summary["clusters"]["sentence"],
        },
        "services": {
            "spearman_rho": services["spearman_rho"],
            "p_perm_two_sided": services["p_perm_two_sided"],
            "caveats": services["caveats"],
            "sentence": services["sentence"],
        },
    }


def export(db_path: Path, out_dir: Path, summary_path: Path = SPATIAL_SUMMARY) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    with duckdb.connect(str(db_path), read_only=True) as con:
        # Relation names and queries are fixed constants above, never user input.
        sources = {name: f"select * from {relation}" for name, relation in EXPORTS.items()}
        for filename, sql in {**sources, **QUERIES}.items():
            target = out_dir / filename
            con.execute(f"copy ({sql}) to '{target.as_posix()}' (format parquet, compression zstd)")
            written.append(target)
        documents = {
            "states.json": states_payload(con),
            "prevalence.json": prevalence_payload(con),
            "spatial.json": spatial_payload(
                con, json.loads(summary_path.read_text(encoding="utf-8"))
            ),
        }
    for filename, document in documents.items():
        path = out_dir / filename
        path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8", newline="\n")
        written.append(path)
    return written


def main() -> int:
    parser = argparse.ArgumentParser(description="Export public dbt marts to Parquet and JSON.")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    for path in export(args.db, args.out_dir):
        print(f"wrote {path.relative_to(ROOT) if path.is_relative_to(ROOT) else path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
