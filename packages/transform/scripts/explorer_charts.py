"""The data explorer's build-time part (P6 item 10): labels, a chart per view, a manifest.

``site/explorer.html`` queries ``dhs2024_state_prevalence.parquet`` and
``dhs2024_national_zone.parquet`` in the browser (DuckDB-WASM) and shows the matching cells in
a sortable table. Everything it shows besides the cells themselves comes from here, written
by ``build_charts.py`` after the other charts:

* ``data/explorer.json``: the human-readable labels of the codes in the files (measures, age
  groups, sexes, levels, precision flags and reasons, the words for cells with no figure),
  taken from the state pages' labels and the marts' YAML, never made up in the page; the
  data dictionary's anchors for the columns; the downloads' provenance (``downloads.DHS``) and
  values rule; and the chart of each view.
* ``data/charts/explorer/<level>-<measure>-<age>-<sex>.json``: one chart document per view
  that has more than one place (each state, or each zone), made by ``disability_access_charts``
  ``dot()`` with its data-derived alt-text and audit. The library has no browser-side
  renderer, so a chart cannot be made at run time without bypassing it; with 84 views
  (7 measures x 2 age groups x 3 sexes x 2 levels) a pre-built set is small (about 2 MB).
  A view of one place shows its level's chart with the place highlighted; Nigeria as a whole
  has one figure per view, so it has no chart.

A chart draws exactly the rows whose table cell shows a figure: suppressed cells, cells with no
data and estimates flagged unreliable (shown as words, as on the state pages) are left out
and named in the manifest. Fewer than two such rows: no chart.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from types import ModuleType
from typing import Any

import duckdb
from disability_access_charts import Series, dot

STATE_FILE = "dhs2024_state_prevalence.parquet"
NATIONAL_ZONE_FILE = "dhs2024_national_zone.parquet"
CHART_DIR = "explorer"  # under data/charts/
MANIFEST = "explorer.json"  # under data/

DHS_SOURCE = "Nigeria DHS 2024 (NPC and ICF), Curb Cut estimates"
VALUE_LABEL = "Share of people (%)"

# (value, label, file). The order is the order of the page's choices.
LEVELS = (
    ("state", "States", STATE_FILE),
    ("zone", "Geopolitical zones", NATIONAL_ZONE_FILE),
    ("national", "Nigeria as a whole", NATIONAL_ZONE_FILE),
)
LEVEL_NOUN = {"state": ("state", "states"), "zone": ("zone", "zones")}
NATIONAL_PLACE = ("NG", "Nigeria")
AGE_GROUPS = (("18+", "Adults 18 and over"), ("5-17", "Children 5 to 17"))
SEXES = (("all", "Both sexes"), ("female", "Female"), ("male", "Male"))

# Measures, from the marts' YAML (measure: "disability3 ... <domain>_3plus: one domain alone at
# that level ... <domain>_level_1 to _level_4 (national only): the share at each level (no
# difficulty, some, a lot, cannot do at all)"). Domain names are the state pages' (DOMAINS).
DISABILITY3_LABEL = (
    "Disability: a lot of difficulty or cannot do at all in at least one of six activities"
)
CUT_OFF = "a lot of difficulty or cannot do at all"
LEVEL_WORDS = ("no difficulty", "some difficulty", "a lot of difficulty", "cannot do at all")

# The precision reasons (curbcut_ingest/precision.py and disclosure.py; the marts' YAML,
# precision_reason). A cell's reason may join several with ";".
REASONS = {
    "low_events<10": "fewer than 10 people with the difficulty in the sample",
    "zero_events": "no one in the sample has the difficulty",
    "all_events": "everyone in the sample has the difficulty",
    "df<8": "fewer than 8 degrees of freedom",
    "n<30": "fewer than 30 respondents",
    "n_effective<30": "an effective sample size under 30",
    "no_interval": "no confidence interval could be computed",
    "ci_width>=0.30": "an interval 30 percentage points wide or more",
    "relative_ci_width>130%": "an interval wider than 130% of the estimate",
    "n<30 (disclosure)": "fewer than 30 respondents (disclosure rule)",
    "complementary suppression (disclosure)": (
        "withheld so that a neighbouring small cell cannot be worked out by subtraction"
    ),
}
# What a cell with no figure shows, in the table, the downloads and the chart's notes.
MISSING = {
    "too_few": "Suppressed (fewer than 30 respondents)",
    "withheld": "Suppressed (withheld to protect a neighbouring small cell)",
    "unreliable": "Not shown: too imprecise (unreliable)",
    "no_data": "No data",
}
# Columns the page explains with a link to the data dictionary.
DICTIONARY_COLUMNS = (
    "estimate",
    "ci_low",
    "ci_high",
    "precision_flag",
    "precision_reason",
    "n_unweighted",
    "suppressed",
)


def _load(name: str) -> ModuleType:
    """A sibling script, registered in sys.modules (its dataclasses need that)."""
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(f"{name}.py"))
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def measure_label(measure: str, domains: Mapping[str, str]) -> str:
    """The label of a measure code; ``ValueError`` for a code the YAML does not describe."""
    if measure == "disability3":
        return DISABILITY3_LABEL
    if measure.endswith("_3plus") and measure in domains:
        return f"{domains[measure]}: {CUT_OFF}"
    prefix, sep, level = measure.rpartition("_level_")
    if sep and f"{prefix}_3plus" in domains and level in {"1", "2", "3", "4"}:
        return f"{domains[f'{prefix}_3plus']}: {LEVEL_WORDS[int(level) - 1]}"
    raise ValueError(f"no label for measure {measure!r}: describe it in the marts' YAML first")


def measure_order(measure: str, domain_codes: list[str]) -> tuple[int, int, int]:
    """DISABILITY3 first, then each activity at the cut-off, then the activities' levels."""
    if measure == "disability3":
        return (0, 0, 0)
    if measure in domain_codes:
        return (1, domain_codes.index(measure), 0)
    prefix, _, level = measure.rpartition("_level_")
    if f"{prefix}_3plus" in domain_codes and level.isdigit():
        return (2, domain_codes.index(f"{prefix}_3plus"), int(level))
    return (3, 0, 0)  # unknown: measure_label refuses it


def load_cells(data_dir: Path) -> list[dict[str, Any]]:
    """Every DHS 2024 cell of both files, one shape: level, place, measure, age group, sex,
    the figures, the flag and whether the cell has data."""
    state = (data_dir / STATE_FILE).as_posix()
    national_zone = (data_dir / NATIONAL_ZONE_FILE).as_posix()
    figures = (
        "measure, age_group, sex, estimate, ci_low, ci_high, n_unweighted, precision_flag, "
        "precision_reason, suppressed"
    )
    sql = (
        f"select 'state' as level, state as place, {figures}, has_data "
        f"from read_parquet('{state}') "
        "union all "
        f"select geography_level as level, geography as place, {figures}, true as has_data "
        f"from read_parquet('{national_zone}')"
    )
    with duckdb.connect() as con:
        cursor = con.execute(sql)
        columns = [d[0] for d in cursor.description]
        return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]


def missing_text(cell: Mapping[str, Any]) -> str | None:
    """The words a cell shows instead of a figure, or None when it shows its figure."""
    if not cell["has_data"]:
        return MISSING["no_data"]
    if cell["suppressed"]:
        reason = str(cell["precision_reason"] or "")
        return MISSING["withheld"] if "complementary" in reason else MISSING["too_few"]
    if cell["precision_flag"] == "unreliable" or cell["estimate"] is None:
        return MISSING["unreliable"]
    return None


def view_key(level: str, measure: str, age_group: str, sex: str) -> str:
    return f"{level}|{measure}|{age_group}|{sex}"


def chart_name(level: str, measure: str, age_group: str, sex: str) -> str:
    """The chart file's name: ``state-disability3-18plus-all``."""
    age = age_group.replace("+", "plus").replace("-", "to")
    return f"{level}-{measure.replace('_', '-')}-{age}-{sex}"


def group_label(age_group: str, sex: str, groups: Iterable[tuple[str, str, str]]) -> str:
    for age, s, label in groups:
        if (age, s) == (age_group, sex):
            return label
    raise ValueError(f"no label for age group {age_group!r} and sex {sex!r}")


def view_chart(
    level: str,
    measure: str,
    age_group: str,
    sex: str,
    cells: Sequence[Mapping[str, Any]],
    *,
    label: str,
    group: str,
) -> tuple[dict[str, Any] | None, list[dict[str, str]]]:
    """The chart of one view (every place of a level) and the places it leaves out."""
    shown: list[Mapping[str, Any]] = []
    left_out: list[dict[str, str]] = []
    for cell in sorted(cells, key=lambda c: str(c["place"])):
        words = missing_text(cell)
        if words is None:
            shown.append(cell)
        else:
            left_out.append({"place": str(cell["place"]), "why": words})
    if len(shown) < 2:
        return None, left_out
    shown.sort(key=lambda c: (-float(c["estimate"]), str(c["place"])))
    singular, plural = LEVEL_NOUN[level]
    doc = dot(
        [str(c["place"]) for c in shown],
        [
            Series(
                VALUE_LABEL,
                tuple(100 * float(c["estimate"]) for c in shown),
                tuple(100 * float(c["ci_low"]) for c in shown),
                tuple(100 * float(c["ci_high"]) for c in shown),
                tuple(str(c["precision_flag"]) for c in shown),
            )
        ],
        title=f"{label}. {group}, by {singular}, with 95% confidence intervals",
        value_label=VALUE_LABEL,
        category_label=singular.capitalize(),
        source=DHS_SOURCE,
        unit="percent",
        decimals=1,
        chart_id=f"explorer_{chart_name(level, measure, age_group, sex).replace('-', '_')}",
    )
    doc["meta"]["places"] = plural
    return doc, left_out


def dictionary_links(dictionary: ModuleType) -> dict[str, dict[str, str]]:
    """For each level, the data dictionary's anchor of each explained column."""
    out = {}
    for level, _, file in LEVELS:
        anchor = dictionary.slug(file)
        out[level] = {
            "file": f"data-dictionary.html#{anchor}",
            **{
                column: f"data-dictionary.html#{dictionary.column_anchor(anchor, column)}"
                for column in DICTIONARY_COLUMNS
            },
        }
    return out


def build(data_dir: Path) -> dict[str, dict[str, Any]]:
    """Write the manifest and the chart documents; return the charts by file name."""
    pages = _load("build_state_pages")
    downloads = _load("downloads")
    dictionary = _load("build_data_dictionary")
    domains = dict(pages.DOMAINS)
    domain_codes = [code for code, _ in pages.DOMAINS]

    cells = load_cells(data_dir)
    measures = sorted(
        {str(c["measure"]) for c in cells}, key=lambda m: measure_order(m, domain_codes)
    )
    for kind, known in (
        ("level", {v for v, _, _ in LEVELS}),
        ("age_group", {v for v, _ in AGE_GROUPS}),
        ("sex", {v for v, _ in SEXES}),
    ):
        unknown = {str(c[kind]) for c in cells} - known
        if unknown:
            raise ValueError(f"no label for {kind} {sorted(unknown)}")
    flags = {*pages.FLAG_TEXT, "suppressed", "no_data"}
    unknown_flags = {str(c["precision_flag"]) for c in cells} - flags
    if unknown_flags:
        raise ValueError(f"no label for precision flag {sorted(unknown_flags)}")

    views: dict[tuple[str, str, str, str], list[dict[str, Any]]] = {}
    for c in cells:
        key = (str(c["level"]), str(c["measure"]), str(c["age_group"]), str(c["sex"]))
        views.setdefault(key, []).append(c)

    out_dir = data_dir / "charts" / CHART_DIR
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)
    docs: dict[str, dict[str, Any]] = {}
    charts: dict[str, dict[str, Any]] = {}
    for (level, measure, age, sex), view_cells in sorted(views.items()):
        if level == "national":
            continue
        doc, left_out = view_chart(
            level,
            measure,
            age,
            sex,
            view_cells,
            label=measure_label(measure, domains),
            group=group_label(age, sex, pages.GROUPS),
        )
        entry: dict[str, Any] = {"left_out": left_out}
        if doc is not None:
            name = chart_name(level, measure, age, sex)
            path = out_dir / f"{name}.json"
            path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8", newline="\n")
            docs[f"{CHART_DIR}/{name}"] = doc
            entry["href"] = f"charts/{CHART_DIR}/{name}.json"
        charts[view_key(level, measure, age, sex)] = entry

    manifest = {
        "levels": [{"value": v, "label": label} for v, label, _ in LEVELS],
        "measures": [{"value": m, "label": measure_label(m, domains)} for m in measures],
        "age_groups": [{"value": v, "label": label} for v, label in AGE_GROUPS],
        "sexes": [{"value": v, "label": label} for v, label in SEXES],
        "groups": {f"{age}|{sex}": label for age, sex, label in pages.GROUPS},
        "places": {"national": {"value": NATIONAL_PLACE[0], "label": NATIONAL_PLACE[1]}},
        "files": {level: file for level, _, file in LEVELS},
        "flags": {**pages.FLAG_TEXT, "suppressed": "Suppressed", "no_data": "No data"},
        "reasons": REASONS,
        "missing": MISSING,
        "dictionary": dictionary_links(dictionary),
        "download": {
            "survey": downloads.DHS.survey,
            "year": downloads.DHS.year,
            "sources": list(downloads.DHS.sources),
            "terms": downloads.DHS.terms,
            "values": downloads.VALUES_RULE,
        },
        "charts": charts,
    }
    (data_dir / MANIFEST).write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n"
    )
    return docs
