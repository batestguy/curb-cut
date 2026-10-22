"""Example 2: a dot plot with 95% confidence intervals, and the claim checker at work.

    python dot_plot_illustrative.py OUTPUT_DIR

ILLUSTRATIVE DATA ONLY. The areas, series and numbers below are synthetic, made up to
show how intervals change what a description may claim. They are not Nigerian figures
and not from any survey.

The script builds the chart, then checks two hand-written claims against its data:

* "For Women, Area A is higher than Area D." passes: the difference is larger than the
  interval test needs.
* "For Women, Area A is higher than Area B." is rejected: Area A's point estimate is
  higher, but the intervals overlap so much that the survey cannot show a difference.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from disability_access_charts import ChartData, Series, check_alt_text, dot, to_csv, to_html

TITLE = "ILLUSTRATIVE ONLY: synthetic prevalence by area and sex (not real data)"
SOURCE = "Synthetic data made up for this example"

AREAS = ["Area A", "Area B", "Area C", "Area D"]
SERIES = [
    Series("Women", (9.8, 9.1, 6.2, 4.0), (8.1, 7.6, 5.0, 3.1), (11.5, 10.6, 7.4, 4.9)),
    Series("Men", (8.9, 7.5, 5.8, 4.4), (7.2, 6.1, 4.7, 3.4), (10.6, 8.9, 6.9, 5.4)),
]

CLAIMS = [
    "For Women, Area A is higher than Area D.",
    "For Women, Area A is higher than Area B.",
]


def main(out_dir: Path) -> int:
    out_dir.mkdir(parents=True, exist_ok=True)
    doc = dot(
        AREAS,
        SERIES,
        title=TITLE,
        value_label="Prevalence (%)",
        category_label="Area",
        source=SOURCE,
        unit="percent",
        chart_id="illustrative_dot",
    )
    path = out_dir / "dot_plot_illustrative.json"
    path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    (out_dir / "dot_plot_illustrative.table.html").write_text(to_html(doc), encoding="utf-8")
    (out_dir / "dot_plot_illustrative.csv").write_text(to_csv(doc), encoding="utf-8")
    print("Alt-text:", doc["alt_text"])
    print("Audit:", "passed" if doc["audit"]["passed"] else "FAILED")

    data = ChartData.from_dict(doc["data"])
    results = []
    for claim in CLAIMS:
        problems = [p for p in check_alt_text(claim, data) if p.severity == "error"]
        results.append(not problems)
        print()
        print(f"Claim: {claim}")
        if not problems:
            print("  PASSES the claim checker")
        for p in problems:
            print(f"  REJECTED ({p.kind}): {p.reason}")
            if p.suggestion:
                print(f"  Suggested wording: {p.suggestion}")
    print(f"\nWrote dot_plot_illustrative.json, .table.html and .csv to {out_dir}")
    # The example is working when the first claim passes and the second is rejected.
    return 0 if doc["audit"]["passed"] and results == [True, False] else 1


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(f"usage: {Path(sys.argv[0]).name} OUTPUT_DIR")
    raise SystemExit(main(Path(sys.argv[1])))
