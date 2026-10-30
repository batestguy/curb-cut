"""Example 4: a choropleth with a pattern per class, written out as a standalone HTML page.

    python choropleth_patterns.py OUTPUT_DIR

ILLUSTRATIVE DATA ONLY. The "map" is a 4 x 3 grid of made-up areas, and the numbers are
synthetic. They are not Nigerian figures and not from any survey.

The script builds the map document, audits it, and writes:

* ``choropleth_patterns.json``: the document (map paths, classes with their patterns,
  themes, alt-text, table, audit);
* ``choropleth_patterns.html``: a page that draws the map the way the document asks: one
  ``role="img"`` named by the alt-text with the SVG hidden from assistive technology, an
  SVG ``<pattern>`` per class over its fill, a legend whose swatches show the same patterns
  with each range in words, and the data table after the map. Light theme only, to keep
  the page short; Curb Cut's site also switches to the dark theme.
"""

from __future__ import annotations

import html
import json
import sys
from pathlib import Path

from disability_access_charts import choropleth, to_html
from disability_access_charts.patterns import get, svg_pattern

TITLE = "ILLUSTRATIVE ONLY: synthetic prevalence by area (not real data)"
SOURCE = "Synthetic data made up for this example"

# A 4 x 3 grid of 100 x 100 squares stands in for real boundaries.
NAMES = [f"Area {chr(ord('A') + i)}" for i in range(12)]
CODES = [f"A{i:02d}" for i in range(12)]
PATHS = {code: f"M{100 * (i % 4)},{100 * (i // 4)}h100v100h-100Z" for i, code in enumerate(CODES)}
VALUES = [1.2, 1.8, 2.4, 2.9, 3.1, 3.6, 4.2, 5.5, 6.3, 7.9, 1.5, 4.8]
LOWER = [0.8, 1.3, 1.9, 2.3, 2.5, 2.9, 3.4, 4.6, 5.1, 6.6, 1.0, 3.9]
UPPER = [1.7, 2.4, 3.0, 3.6, 3.8, 4.4, 5.1, 6.5, 7.6, 9.3, 2.1, 5.8]


def page(doc: dict) -> str:
    """A minimal page for the light theme (see the module docstring)."""
    theme = doc["themes"]["light"]
    ink = doc["patterns"]["ink"]["light"]
    scale = doc["patterns"]["scale"]
    defs = "".join(
        svg_pattern(
            get(c["pattern"]),
            pattern_id=f"p{k}",
            ink=ink,
            fill=theme["classes"][k],
            scale=scale,
        )
        + svg_pattern(get(c["pattern"]), pattern_id=f"l{k}", ink=ink, fill=theme["classes"][k])
        for k, c in enumerate(doc["classes"])
    )
    regions = "".join(
        f'<path d="{doc["map"]["paths"][r["code"]]}" fill="url(#p{r["class"]})" '
        f'stroke="{theme["edge"]}"/>'
        for r in doc["regions"]
    )
    legend = "".join(
        f'<li><svg width="24" height="16" aria-hidden="true" focusable="false">'
        f'<rect width="24" height="16" fill="url(#l{k})" stroke="{theme["edge"]}"/></svg> '
        f"{html.escape(c['label'])}: {c['count']} areas</li>"
        for k, c in enumerate(doc["classes"])
    )
    return f"""<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>{html.escape(doc["title"])}</title></head>
<body style="background:{theme["background"]};color:{theme["text"]};font-family:sans-serif">
<h1>{html.escape(doc["title"])}</h1>
<ul style="list-style:none;padding:0">{legend}</ul>
<div role="img" aria-label="{html.escape(doc["alt_text"], quote=True)}" style="max-width:40rem">
<svg viewBox="{doc["map"]["viewBox"]}" aria-hidden="true" focusable="false">
<defs>{defs}</defs>{regions}</svg>
</div>
{to_html(doc)}</body>
</html>
"""


def main(out_dir: Path) -> int:
    out_dir.mkdir(parents=True, exist_ok=True)
    doc = choropleth(
        NAMES,
        CODES,
        VALUES,
        lower=LOWER,
        upper=UPPER,
        paths=PATHS,
        view_box="0 0 400 300",
        breaks=[2, 3, 4, 6],
        title=TITLE,
        value_label="Prevalence (%)",
        category_label="Area",
        source=SOURCE,
        chart_id="illustrative_map",
    )
    (out_dir / "choropleth_patterns.json").write_text(
        json.dumps(doc, indent=2) + "\n", encoding="utf-8"
    )
    (out_dir / "choropleth_patterns.html").write_text(page(doc), encoding="utf-8")
    print("Alt-text:", doc["alt_text"])
    for c in doc["classes"]:
        print(f"  {c['label']}: {c['count']} areas, pattern {c['pattern']}")
    print("Audit:", "passed" if doc["audit"]["passed"] else "FAILED")
    print(f"\nWrote choropleth_patterns.json and .html to {out_dir}")
    return 0 if doc["audit"]["passed"] else 1


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(f"usage: {Path(sys.argv[0]).name} OUTPUT_DIR")
    raise SystemExit(main(Path(sys.argv[1])))
