"""Build the site's chart documents from the exported Parquet marts.

Run after ``export_marts.py``, from the repo root:
``uv run python packages/transform/scripts/build_charts.py``.

Each chart goes through ``disability_access_charts`` so it carries data-derived alt-text,
a data table and a contrast audit. The build fails if any audit fails.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import duckdb
from disability_access_charts.experimental import bar_chart

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DATA = ROOT / "site" / "public" / "data"

SOURCE = "JONAPWD, 2025 Assumptive Disability Disaggregated Data"


def national_by_type(data_dir: Path) -> dict:
    parquet = (data_dir / "jonapwd_national_by_type.parquet").as_posix()
    rows = duckdb.sql(
        "select disability_type_label, persons "
        f"from read_parquet('{parquet}') order by persons desc, sort_order"
    ).fetchall()
    return bar_chart(
        [str(label) for label, _ in rows],
        [int(persons) for _, persons in rows],
        title="Persons with disabilities by type, all 37 states (JONAPWD estimates)",
        value_label="Persons",
        category_label="Disability type",
        source=SOURCE,
        chart_id="national_by_type",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Build chart JSON documents for the site.")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA)
    args = parser.parse_args()
    out_dir = args.data_dir / "charts"
    out_dir.mkdir(parents=True, exist_ok=True)

    failed = False
    for name, doc in {"national_by_type": national_by_type(args.data_dir)}.items():
        path = out_dir / f"{name}.json"
        path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8", newline="\n")
        status = "passed" if doc["audit"]["passed"] else "FAILED"
        print(f"wrote {path} (audit {status})")
        failed = failed or not doc["audit"]["passed"]
    if failed:
        print("A chart failed its accessibility audit.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
