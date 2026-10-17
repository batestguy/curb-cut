"""Export the public dbt marts from DuckDB to Parquet for the static site.

Run after ``dbt build``, from the repo root:
``uv run python packages/transform/scripts/export_marts.py``.

Opens the warehouse read-only, so it never competes with a dbt writer. Outputs are build
artefacts (git-ignored) under ``site/public/data/``, which Vite copies into the site.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DB = ROOT / "data" / "curbcut.duckdb"
DEFAULT_OUT = ROOT / "site" / "public" / "data"

# Only public, aggregate marts belong here. Parquet file name -> relation in the warehouse.
EXPORTS = {
    "jonapwd_state_by_type.parquet": "mart_jonapwd_state_by_type",
    "jonapwd_national_by_type.parquet": "mart_jonapwd_national_by_type",
}


def export(db_path: Path, out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    with duckdb.connect(str(db_path), read_only=True) as con:
        for filename, relation in EXPORTS.items():
            target = out_dir / filename
            # Relation names are fixed constants above, never user input.
            con.execute(
                f"copy (select * from {relation}) to '{target.as_posix()}' "
                "(format parquet, compression zstd)"
            )
            written.append(target)
        # The state list for the picker, plus the state card's facts (small: 37 rows).
        cursor = con.execute(
            "select state, state_code, zone, capital, capital_source_url, slogan, "
            "slogan_source_url, population_2023, jonapwd_total, share_of_national, rank_of_37 "
            "from mart_state_profile order by state"
        )
        columns = [d[0] for d in cursor.description]
        payload = [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]
    states_path = out_dir / "states.json"
    states_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8", newline="\n")
    written.append(states_path)
    return written


def main() -> int:
    parser = argparse.ArgumentParser(description="Export public dbt marts to Parquet.")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    for path in export(args.db, args.out_dir):
        print(f"wrote {path.relative_to(ROOT) if path.is_relative_to(ROOT) else path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
