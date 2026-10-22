"""Example 3: audit an ordinary Plotly figure, fix what it finds, and audit it again.

    python audit_plotly_figure.py OUTPUT_DIR

Uses Plotly if it is installed (``pip install "disability-access-charts[plotly]"``) and a
plain figure dict otherwise; the audit treats both the same way. The numbers are made up
for the example.

The first figure has the usual problems: Okabe-Ito yellow bars (1.3:1 on white, below
SC 1.4.11's 3:1), hover tooltips on, zoom and pan on, and alt-text that names the wrong
largest bar. The second fixes them with ``theme()``, a static layout and alt-text that
matches the data.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from disability_access_charts import audit, theme

CATEGORIES = ["North", "South", "East", "West"]
VALUES = [42, 35, 28, 19]
TITLE = "Example: requests by region (made-up numbers)"


def make_figure() -> Any:
    spec = {
        "data": [
            {
                "type": "bar",
                "x": CATEGORIES,
                "y": VALUES,
                "marker": {"color": "#f0e442"},
                "hovertemplate": "%{x}: %{y}<extra></extra>",
            }
        ],
        "layout": {"title": {"text": TITLE}},
    }
    try:
        import plotly
        import plotly.graph_objects as go
    except ImportError:
        print("(Plotly not installed: auditing a plain figure dict)")
        return spec
    print(f"(Auditing a plotly.graph_objects.Figure, Plotly {plotly.__version__})")
    return go.Figure(spec)


def summary(result: dict[str, Any]) -> list[str]:
    lines = [f"passed: {result['passed']}, warnings: {result['warnings']}"]
    for c in result["checks"]:
        if not c["passed"]:
            lines.append(f"  {c['severity']}: {c['id']} (WCAG {c['wcag']}): {c['description']}")
            for p in c.get("problems", []):
                lines.append(f"    - {p['reason']}")
    return lines


def main(out_dir: Path) -> int:
    out_dir.mkdir(parents=True, exist_ok=True)
    fig = make_figure()
    before = audit(fig, alt_text=f"{TITLE}. Largest: South, 42.", has_table=False)
    print("Before:")
    print("\n".join(summary(before)))

    fixed = theme(fig, "light")
    spec = fixed.to_plotly_json() if hasattr(fixed, "to_plotly_json") else fixed
    for trace in spec["data"]:
        trace.pop("hovertemplate", None)
        trace["hoverinfo"] = "skip"
    spec["layout"]["xaxis"] = {**spec["layout"].get("xaxis", {}), "fixedrange": True}
    spec["layout"]["yaxis"] = {**spec["layout"].get("yaxis", {}), "fixedrange": True}
    after = audit(spec, alt_text=f"{TITLE}. Largest: North, 42. Smallest: West, 19.")
    print("\nAfter:")
    print("\n".join(summary(after)))

    (out_dir / "audit_before.json").write_text(json.dumps(before, indent=2) + "\n", "utf-8")
    (out_dir / "audit_after.json").write_text(json.dumps(after, indent=2) + "\n", "utf-8")
    print(f"\nWrote audit_before.json and audit_after.json to {out_dir}")
    return 0 if not before["passed"] and after["passed"] else 1


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(f"usage: {Path(sys.argv[0]).name} OUTPUT_DIR")
    raise SystemExit(main(Path(sys.argv[1])))
