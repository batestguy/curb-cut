"""Build the site's chart documents from the exported Parquet marts.

Run after ``export_marts.py``, from the repo root:
``uv run python packages/transform/scripts/build_charts.py``.

Each chart goes through ``disability_access_charts`` so it carries data-derived alt-text,
a data table and an accessibility audit. The build fails if any audit fails.

* ``prevalence_map``: DHS 2024 DISABILITY3, adults 18+, by state, in fixed classes, as a
  choropleth document with a pattern per class (``disability_access_charts.choropleth``)
  drawn with the same projected paths as the locator map (``build_map.py``);
* ``prevalence_by_state``: the same 37 estimates with their 95% intervals and precision
  flags, as a dot plot, with the library's statistical findings (each state against the
  next in the ranking and against the national estimate, false discovery rate 5%);
  Both carry their description in Hausa, Yoruba, Igbo and Pidgin
  (``alt_text_translations``, P6 item 8), from the library's templates and the site's
  strings in ``packages/transform/translations.yml`` (``translations.py``); the strings
  for the page's disclosure go to ``translations.json``;
* ``national_by_type`` and ``national_by_state``: JONAPWD's assumed figures, as bars;
* ``poverty_headline`` and ``poverty_dimensions`` (P5, from ``poverty.json``): the five
  headline estimates and the four MPI dimensions (S4), each with its 95% interval, as dot
  plots in percentage points (or score points out of 100). ``findings=False``: comparisons
  between these estimates were not pre-registered. The library has no percentage-point unit,
  so ``unit="number"`` is used with the unit in the value label.

It also writes the main page's table downloads (``main_page_downloads``) to
``downloads/main/`` with a manifest, ``downloads/main/index.json``, that the page reads, and
the data explorer's chart set and manifest (``explorer_charts.py``: ``charts/explorer/`` and
``explorer.json``) and the sensitivity page's (``sensitivity_data.py``: ``charts/sensitivity/``
and ``sensitivity.json``).
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from pathlib import Path
from types import ModuleType

import duckdb
from disability_access_charts import Reference, Series, audit, bar, choropleth, dot

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DATA = ROOT / "site" / "public" / "data"
# The live site, for the downloads' page URL (as build_state_pages.py). Override: SITE_URL.
DEFAULT_SITE_URL = "https://batestguy.github.io/curb-cut/"

SOURCE = "JONAPWD, 2025 Assumptive Disability Disaggregated Data"
DHS_SOURCE = "Nigeria DHS 2024 (NPC and ICF), Curb Cut estimates"

# Fixed, rounded classes for the prevalence map (author, 2026-10-28): under 2%, 2-3%, 3-4%,
# 4-6%, 6% and over. With the DHS 2024 state estimates (0.8% to 11.3%) every class has
# states (12, 11, 4, 6 and 4); the audit warns if one is ever empty.
MAP_BREAKS = (2, 3, 4, 6)

PREVALENCE_LABEL = "Adults with disability (%)"
# The overall value each state is compared with in the findings. "Nigeria as a whole" rather
# than "national estimate": the claim checker reads "estimate" as a hedge word.
NATIONAL_LABEL = "Nigeria as a whole"
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


def _load_sibling(name: str) -> ModuleType:
    """A sibling script, registered in sys.modules (its dataclasses need that)."""
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(f"{name}.py"))
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
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


def withheld_states(data_dir: Path) -> list[str]:
    """States with no published DISABILITY3 18+ cell (suppressed or no data), by name."""
    parquet = (data_dir / "dhs2024_state_prevalence.parquet").as_posix()
    rows = duckdb.sql(
        "select state from read_parquet('" + parquet + "') "
        "where measure = 'disability3' and age_group = '18+' and sex = 'all' "
        "and not (has_data and not suppressed) order by state"
    ).fetchall()
    return [str(r[0]) for r in rows]


def national_reference(data_dir: Path) -> Reference:
    """The national DISABILITY3 18+ estimate, as percentages, for the findings."""
    parquet = (data_dir / "dhs2024_national_zone.parquet").as_posix()
    row = duckdb.sql(
        "select 100 * estimate, 100 * ci_low, 100 * ci_high "
        f"from read_parquet('{parquet}') "
        "where geography_level = 'national' and measure = 'disability3' "
        "and age_group = '18+' and sex = 'all' and not suppressed"
    ).fetchone()
    if row is None:
        raise SystemExit("no national DISABILITY3 18+ estimate in the export")
    return Reference(NATIONAL_LABEL, float(row[0]), float(row[1]), float(row[2]))


def glossary() -> object:
    """The site's translated strings (translations.yml); fails if a language is missing."""
    return _load_sibling("translations").load()


def prevalence_by_state(data_dir: Path) -> dict:
    rows = headline_rows(data_dir)
    tr = _load_sibling("translations")
    return dot(
        [str(r[0]) for r in rows],
        [
            Series(
                PREVALENCE_LABEL,
                tuple(float(r[2]) for r in rows),
                tuple(float(r[3]) for r in rows),
                tuple(float(r[4]) for r in rows),
                tuple(str(r[5]) for r in rows),
            )
        ],
        title="Disability among adults 18+ by state, with 95% confidence intervals",
        value_label=PREVALENCE_LABEL,
        category_label="State",
        source=DHS_SOURCE,
        unit="percent",
        decimals=1,
        chart_id="prevalence_by_state",
        findings=True,
        reference=national_reference(data_dir),
        withheld=withheld_states(data_dir),
        translations=tr.translations(
            glossary(), title="dots_title", category="state_label", reference=True
        ),
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
        translations=_load_sibling("translations").translations(
            glossary(), title="map_title", category="state_label"
        ),
    )


POVERTY_SOURCE = "NBS MPI 2021, Curb Cut estimates (pre-registered, OSF kes3p)"
# (estimate_id, chart label). Labels avoid "estimate", which the claim checker reads as a
# hedge word.
POVERTY_HEADLINE = (
    ("primary", "All households (primary)"),
    ("overlap_population", "Better-supported comparison (overlap)"),
    ("survey_lpm", "Survey-weighted linear model"),
    ("s2_broad", "NBS's broad definition (S2)"),
    ("s3_head", "Household head has the difficulty (S3)"),
)
POVERTY_DIMENSIONS = (
    ("s4_health", "Health"),
    ("s4_education", "Education"),
    ("s4_living_standards", "Living standards"),
    ("s4_work_and_shocks", "Work and shocks"),
)


def _poverty_dot(
    payload: dict,
    rows: tuple[tuple[str, str], ...],
    *,
    title: str,
    value_label: str,
    chart_id: str,
    unit_words: str,
) -> dict:
    """A dot plot of P5 estimates, x100 (percentage points or score points), with intervals.

    Every listed estimate must be published: the page has no chart without them.
    """
    found = [(label, payload["estimates"][eid]) for eid, label in rows]
    hidden = [label for label, e in found if e["suppressed"]]
    if hidden:
        raise SystemExit(f"{chart_id}: suppressed estimates {hidden}; no chart")
    doc = dot(
        [label for label, _ in found],
        [
            Series(
                value_label,
                tuple(100 * e["estimate"] for _, e in found),
                tuple(100 * e["ci_low"] for _, e in found),
                tuple(100 * e["ci_high"] for _, e in found),
            )
        ],
        title=title,
        value_label=value_label,
        category_label="Comparison",
        source=POVERTY_SOURCE,
        unit="number",
        decimals=1,
        chart_id=chart_id,
        findings=False,
    )
    return neutral_alt_text(doc, unit_words)


def _fixed(value: float) -> str:
    text = f"{value:.1f}"
    return text.lstrip("-") if float(text) == 0 else text


def neutral_alt_text(doc: dict, unit_words: str) -> dict:
    """Replace describe()'s alt-text with a neutral one built from the document's own data.

    describe() names the highest and lowest estimates and whether the survey can show a
    difference from the next one. These estimates come from one sample (not independent
    groups), and no comparison between them was pre-registered, so the poverty charts say
    only what each estimate and interval is, in table order, every row. The audit is rerun on
    the new text (alt-text-matches-data must still pass).
    """
    data = doc["data"]
    series = data["series"][0]
    items = "; ".join(
        f"{name} {_fixed(v)} {unit_words} (95% confidence interval {_fixed(lo)} to {_fixed(hi)})"
        for name, v, lo, hi in zip(
            data["categories"], series["values"], series["lower"], series["upper"], strict=True
        )
    )
    n = len(data["categories"])
    doc["alt_text"] = (
        f"Dot plot: {doc['title']}. {n} dots, in table order: {items}. "
        f"Source: {doc['meta']['source']}."
    )
    doc["audit"] = audit(doc)
    return doc


def poverty_charts(data_dir: Path) -> dict[str, dict]:
    payload = json.loads((data_dir / "poverty.json").read_text(encoding="utf-8"))
    return {
        "poverty_headline": _poverty_dot(
            payload,
            POVERTY_HEADLINE,
            title=(
                "How much more likely people in households with a severely disabled member "
                "are to be multidimensionally poor, five ways, with 95% confidence intervals"
            ),
            value_label="Difference (percentage points)",
            chart_id="poverty_headline",
            unit_words="percentage points",
        ),
        "poverty_dimensions": _poverty_dot(
            payload,
            POVERTY_DIMENSIONS,
            title=(
                "Where the difference sits: each MPI dimension's part of the deprivation "
                "score, with 95% confidence intervals"
            ),
            value_label="Difference (points out of 100)",
            chart_id="poverty_dimensions",
            unit_words="points",
        ),
    }


def main_page_downloads(docs: dict[str, dict], data_dir: Path, site_url: str) -> Path:
    """The main page's table downloads (``downloads.py``), written from the same table specs
    the page renders: the two DHS chart documents' tables and the Moran table in
    ``spatial.json``. ``downloads/main/index.json`` tells the page each table's links. The
    JONAPWD tables get none (all rights reserved; the page cites the publication instead)."""
    downloads = _load_sibling("downloads")
    if not site_url.endswith("/"):
        site_url += "/"
    collector = downloads.Collector(site_url, "main", "downloads/")
    spatial = json.loads((data_dir / "spatial.json").read_text(encoding="utf-8"))
    for table_id, spec, name, provenance in (
        (
            "prevalence-map",
            docs["prevalence_map"]["table"],
            "adults with disability by state, with map classes",
            downloads.DHS,
        ),
        (
            "prevalence-by-state",
            docs["prevalence_by_state"]["table"],
            "adults with disability by state, highest first",
            downloads.DHS,
        ),
        (
            "moran",
            spatial["moran_table"],
            "Moran's I by measure (clustering across the country)",
            downloads.DHS_SPATIAL,
        ),
    ):
        collector.add(downloads.from_spec(spec, table_id, name, provenance))
    return downloads.write_manifest(collector, data_dir / "downloads")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build chart JSON documents for the site.")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA)
    parser.add_argument(
        "--site-url",
        default=os.environ.get("SITE_URL", DEFAULT_SITE_URL),
        help="the live site, for the downloads' page URL",
    )
    args = parser.parse_args()
    out_dir = args.data_dir / "charts"
    out_dir.mkdir(parents=True, exist_ok=True)

    failed = False
    docs = {
        "prevalence_map": prevalence_map(args.data_dir, _load_build_map()),
        "prevalence_by_state": prevalence_by_state(args.data_dir),
        "national_by_type": national_by_type(args.data_dir),
        "national_by_state": national_by_state(args.data_dir),
        **poverty_charts(args.data_dir),
    }
    for name, doc in docs.items():
        path = out_dir / f"{name}.json"
        path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8", newline="\n")
        status = "passed" if doc["audit"]["passed"] else "FAILED"
        print(f"wrote {path} (audit {status}, {doc['audit']['warnings']} warning(s))")
        failed = failed or not doc["audit"]["passed"]
    # The data explorer's charts (one per view) and its manifest; explorer_charts.build writes
    # them into charts/explorer/ (cleared first) and explorer.json. Audited like the others.
    explorer_docs = _load_sibling("explorer_charts").build(args.data_dir)
    for name, doc in explorer_docs.items():
        failed = failed or not doc["audit"]["passed"]
        if not doc["audit"]["passed"]:
            print(f"explorer chart {name}: audit FAILED", file=sys.stderr)
    print(f"wrote {len(explorer_docs)} explorer charts and {args.data_dir / 'explorer.json'}")
    # The sensitivity page's charts (one per age group and assumed rate) and its manifest;
    # sensitivity_data.build writes them into charts/sensitivity/ (cleared first) and
    # sensitivity.json. Audited like the others.
    sensitivity_docs = _load_sibling("sensitivity_data").build(args.data_dir)
    for name, doc in sensitivity_docs.items():
        failed = failed or not doc["audit"]["passed"]
        if not doc["audit"]["passed"]:
            print(f"sensitivity chart {name}: audit FAILED", file=sys.stderr)
    print(
        f"wrote {len(sensitivity_docs)} sensitivity charts and {args.data_dir / 'sensitivity.json'}"
    )
    if failed:
        print("A chart failed its accessibility audit.", file=sys.stderr)
        return 1
    print(f"wrote {main_page_downloads(docs, args.data_dir, args.site_url)} and its tables' files")
    ui = _load_sibling("translations").ui_json(glossary())
    path = args.data_dir / "translations.json"
    path.write_text(
        json.dumps(ui, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n"
    )
    print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
