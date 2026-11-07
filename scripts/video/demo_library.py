"""Act 5b demo: disability-access-charts checking claims against the real state chart."""

import json
from pathlib import Path

from disability_access_charts import ChartData, check_alt_text

ROOT = Path(__file__).resolve().parents[2]

doc = json.loads(
    (ROOT / "site/public/data/charts/prevalence_by_state.json").read_text(encoding="utf-8")
)
data = ChartData.from_dict(doc["data"])

print(doc["alt_text"][:205] + " ...")
print(
    doc["findings"]["checked"], "comparisons checked,", doc["findings"]["supported"], "supported\n"
)

for claim in ["Taraba has a higher rate than Lagos.", "Taraba has a higher rate than Abia."]:
    problems = check_alt_text(claim, data)
    print(">>>", claim)
    print("    OK" if not problems else f"    REJECTED: {problems[0].reason}")
