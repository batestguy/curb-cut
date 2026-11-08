"""Run each step's code for real and record what it prints (the GIF shows exactly this).

Run with the Python of a fresh environment where disability-access-charts was installed
from PyPI, passing the saved output of that pip install:

    python frames.py pip.txt   # writes chart.json and frames.json here
"""

import contextlib
import io
import json
import subprocess
import sys
from pathlib import Path

# ruff: noqa: E501  (captions and code are shown verbatim in the GIF)

steps = [
    (
        "Install it from PyPI. The core has no dependencies.",
        "shell",
        "pip install disability-access-charts",
        Path(sys.argv[1]).read_text(encoding="utf-8").strip(),
    ),
    (
        "Give each estimate its 95% confidence interval. (These numbers are made up, for illustration.)",
        "python",
        """from disability_access_charts import ChartData, Series, check_alt_text, dot

areas = ["Area A", "Area B", "Area D"]
women = Series("Women", values=(9.8, 9.1, 4.0),
               lower=(8.1, 7.6, 3.1),     # 95% confidence interval
               upper=(11.5, 10.6, 4.9))""",
        None,
    ),
    (
        "Build the chart. dot() returns one JSON document: the Plotly spec, the description, a data table and an audit.",
        "python",
        """doc = dot(areas, [women], title="Synthetic prevalence (not real data)",
          value_label="Prevalence (%)", category_label="Area",
          source="Synthetic", unit="percent")
print(list(doc))""",
        None,
    ),
    (
        "Read the description. It is written from the data, and says only what the intervals support.",
        "python",
        """print(doc["alt_text"])""",
        None,
    ),
    (
        "The audit: every check names its WCAG success criterion (contrast, text alternative, keyboard).",
        "python",
        """audit = doc["audit"]
print("passed:", audit["passed"], "| checks:", len(audit["checks"]),
      "| warnings:", audit["warnings"])
for c in audit["checks"][8:12]:
    print(" ", c["id"], "WCAG", c["wcag"], "passed" if c["passed"] else "FAILED")""",
        None,
    ),
    (
        "Check any sentence against the data. An empty list means no problems were found.",
        "python",
        """data = ChartData.from_dict(doc["data"])
print(check_alt_text("Area A is higher than Area D.", data))""",
        None,
    ),
    (
        "A claim the data cannot support is rejected, with the reason and a safer wording.",
        "python",
        """for p in check_alt_text("Area A is higher than Area B.", data):
    print(p.severity + ":", p.reason)
    print("suggestion:", p.suggestion)""",
        None,
    ),
    (
        "In CI: audit every chart file. Any failure exits 1; with --strict, so does any warning.",
        "shell",
        "disability-access-charts check --strict chart.json",
        None,
    ),
]
ns, out = {}, []
for caption, kind, code, given in steps:
    if kind == "python":
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            exec(code, ns)
        result = buf.getvalue().rstrip()
        if "doc" in ns:
            Path("chart.json").write_text(json.dumps(ns["doc"]), encoding="utf-8")
    else:
        result = given
    out.append({"caption": caption, "kind": kind, "code": code, "output": result})
cli = Path(sys.executable).parent / "disability-access-charts"
r = subprocess.run([str(cli), "check", "--strict", "chart.json"], capture_output=True, text=True)
out[-1]["output"] = (r.stdout + r.stderr).strip() + f"\n(exit code {r.returncode})"
Path("frames.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
for f in out:
    print("==", f["caption"])
    print(f["output"])
