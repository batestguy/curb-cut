"""Example 1: a bar chart of JONAPWD's 2025 national figures, by disability type.

    python jonapwd_bar.py OUTPUT_DIR

Writes the chart document (JSON), its table as HTML and CSV, and prints the alt-text and
the audit result.

The figures are JONAPWD's *assumed* figures for all 37 states, from its "Assumptive
Disability Disaggregated Data" (2025): a WHO 15% disability-prevalence benchmark applied to
population, split by type. They are not measured or published survey estimates. They are
cited here, not computed, and this is the only example with real-world figures; the
installed package itself holds no data.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from disability_access_charts import bar, to_csv, to_html

SOURCE = "JONAPWD, 2025 Assumptive Disability Disaggregated Data"
FIGURES = {
    "Physical disability": 8186521,
    "Hearing impairment": 7653482,
    "Visual impairment": 7187637,
    "Affected by leprosy": 2818330,
    "Albinism": 2781922,
    "Spinal cord injury": 2532418,
    "Intellectual disability": 2487588,
    "Others": 1101077,
    "Deaf-blindness": 90920,
    "Little stature": 61511,
}


def main(out_dir: Path) -> int:
    out_dir.mkdir(parents=True, exist_ok=True)
    doc = bar(
        list(FIGURES),
        list(FIGURES.values()),
        title="Persons with disabilities by type, all 37 states (JONAPWD assumed figures)",
        value_label="Persons",
        category_label="Disability type",
        source=SOURCE,
        chart_id="jonapwd_by_type",
    )
    (out_dir / "jonapwd_bar.json").write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    (out_dir / "jonapwd_bar.table.html").write_text(to_html(doc), encoding="utf-8")
    (out_dir / "jonapwd_bar.csv").write_text(to_csv(doc), encoding="utf-8")
    print("Alt-text:", doc["alt_text"])
    print("Audit:", "passed" if doc["audit"]["passed"] else "FAILED")
    print(f"Wrote jonapwd_bar.json, .table.html and .csv to {out_dir}")
    return 0 if doc["audit"]["passed"] else 1


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(f"usage: {Path(sys.argv[0]).name} OUTPUT_DIR")
    raise SystemExit(main(Path(sys.argv[1])))
