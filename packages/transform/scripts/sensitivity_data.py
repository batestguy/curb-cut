"""The sensitivity page's build-time part (P6 item 11): an assumed rate against the survey.

JONAPWD's 2025 state figures apply one assumed rate (15%, WHO's global figure) to every state's
projected population. ``site/sensitivity.html`` lets the reader change that rate and shows,
state by state, where it falls against the DHS 2024 survey's estimate and 95% confidence
interval. Everything it shows comes from here, written by ``build_charts.py`` after the
explorer's charts:

* ``data/sensitivity.json``: the DISABILITY3 cells for both sexes in each age group (from
  ``dhs2024_state_prevalence.parquet``), the state's 2023 population projection (all ages),
  the assumed and global figures with their wording (``prevalence_comparison.parquet``), the
  definitions in the data dictionary's words (the marts' YAML), the explorer's words for cells
  with no figure, the downloads' provenance and the chart of each age group and rate.
* ``data/charts/sensitivity/<age>-rate-<r>.json``: one ``disability_access_charts`` ``dot()``
  document per age group and assumed rate (2 x 37 = 74): the survey estimates with their
  intervals, and the assumed rate as a second series with the same value in every row. The
  library draws no reference line and has no browser-side renderer, so the set is pre-built;
  each document has its data-derived alt-text and audit. The interval label says that only
  the survey estimates have intervals.

Only DISABILITY3 is offered: the state file holds no broader Washington Group measure (no
"some difficulty or worse" for all activities together), only each activity alone at the
same cut-off. Survey figures stay rates of one age group; only the assumption becomes a count
(rate x the all-ages projection), on the page, labelled as such.
"""

from __future__ import annotations

import importlib.util
import json
import re
import shutil
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from types import ModuleType
from typing import Any

import duckdb
from disability_access_charts import Series, dot

STATE_FILE = "dhs2024_state_prevalence.parquet"
COMPARISON_FILE = "prevalence_comparison.parquet"
MANIFEST = "sensitivity.json"  # under data/
CHART_DIR = "sensitivity"  # under data/charts/
MEASURE = "disability3"

# The slider's rates, in percent: 2 to 20 in steps of 0.5 (37 rates); JONAPWD's 15% first.
RATE_MIN = 2.0
RATE_MAX = 20.0
RATE_STEP = 0.5
DEFAULT_RATE = 15.0

# (value, label, short label for the summary sentence). Both sexes only: the assumption is
# applied to everyone. An en dash in the ages, as on the state pages.
AGE_GROUPS = (
    ("18+", "Adults 18 and over", "adults 18+"),
    ("5-17", "Children 5 to 17", "children 5–17"),  # noqa: RUF001
)
SURVEY_SERIES = "DHS 2024 survey estimate"
ASSUMED_SERIES = "Assumed rate"
VALUE_LABEL = "Share of people (%)"
INTERVAL_LABEL = "95% confidence interval, survey estimates only"
ASSUMPTION_ID = "jonapwd_2025"
GLOBAL_ID = "who_2023"
# The data dictionary columns the page links to.
DICTIONARY_COLUMNS = ("estimate", "ci_low", "ci_high", "precision_flag", "population_2023")


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


def rates() -> list[float]:
    """Every rate the slider offers, in percent."""
    count = round((RATE_MAX - RATE_MIN) / RATE_STEP)
    return [RATE_MIN + i * RATE_STEP for i in range(count + 1)]


def rate_key(rate: float) -> str:
    """A rate as the manifest's chart keys write it: ``15.0`` (JavaScript ``toFixed(1)``)."""
    return f"{rate:.1f}"


def chart_name(age_group: str, rate: float) -> str:
    """The chart file's name: ``18plus-rate-15-0``."""
    age = age_group.replace("+", "plus").replace("-", "to")
    return f"{age}-rate-{rate_key(rate).replace('.', '-')}"


def load_cells(data_dir: Path) -> dict[str, list[dict[str, Any]]]:
    """DISABILITY3, both sexes, every state, by age group; with the state's population."""
    path = (data_dir / STATE_FILE).as_posix()
    sql = (
        "select age_group, state, estimate, ci_low, ci_high, n_unweighted, precision_flag, "
        "precision_reason, suppressed, has_data, population_2023 "
        f"from read_parquet('{path}') where measure = ? and sex = 'all' "
        "order by age_group, state"
    )
    with duckdb.connect() as con:
        cursor = con.execute(sql, [MEASURE])
        columns = [d[0] for d in cursor.description]
        rows = [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]
    out: dict[str, list[dict[str, Any]]] = {age: [] for age, _, _ in AGE_GROUPS}
    for row in rows:
        age = str(row.pop("age_group"))
        if age not in out:
            raise ValueError(f"no label for age group {age!r}")
        out[age].append(row)
    for age, cells in out.items():
        if not cells:
            raise ValueError(f"no {MEASURE} cells for age group {age!r}")
    return out


def load_figures(data_dir: Path) -> dict[str, dict[str, Any]]:
    """The comparison rows the page quotes (the main page's wording), by figure id."""
    path = (data_dir / COMPARISON_FILE).as_posix()
    with duckdb.connect() as con:
        cursor = con.execute(
            "select figure_id, label, kind, value_percent, ci_low_percent, ci_high_percent, "
            f"population, definition, source, source_url from read_parquet('{path}')"
        )
        columns = [d[0] for d in cursor.description]
        rows = {str(r[0]): dict(zip(columns, r, strict=True)) for r in cursor.fetchall()}
    missing = {ASSUMPTION_ID, GLOBAL_ID} - set(rows)
    if missing:
        raise ValueError(f"{COMPARISON_FILE} lacks {sorted(missing)}")
    return rows


def first_sentence_about(description: str, code: str) -> str:
    """The clause of a measure description that defines ``code`` ("disability3: the ...")."""
    match = re.search(rf"\b{re.escape(code)}: ([^.]*\.)", description)
    if not match:
        raise ValueError(f"the marts' YAML does not define {code!r}")
    text = match.group(1)
    return text[0].upper() + text[1:]


def survey_cell(cell: Mapping[str, Any]) -> dict[str, Any]:
    """A cell as the page reads it (proportions, as in the Parquet file)."""
    n = cell["n_unweighted"]
    pop = cell["population_2023"]
    return {
        "state": str(cell["state"]),
        "estimate": cell["estimate"],
        "ci_low": cell["ci_low"],
        "ci_high": cell["ci_high"],
        "n_unweighted": None if n is None else int(n),
        "precision_flag": str(cell["precision_flag"]),
        "precision_reason": cell["precision_reason"],
        "suppressed": bool(cell["suppressed"]),
        "has_data": bool(cell["has_data"]),
        "population_2023": None if pop is None else int(pop),
    }


def rate_chart(
    age_group: str,
    rate: float,
    cells: Sequence[Mapping[str, Any]],
    *,
    group: str,
    missing_text: Any,
) -> tuple[dict[str, Any] | None, list[dict[str, str]]]:
    """The chart of one age group at one assumed rate, and the states it leaves out (the
    same as the explorer: suppressed, no data, unreliable)."""
    shown: list[Mapping[str, Any]] = []
    left_out: list[dict[str, str]] = []
    for cell in sorted(cells, key=lambda c: str(c["state"])):
        words = missing_text(cell)
        if words is None:
            shown.append(cell)
        else:
            left_out.append({"place": str(cell["state"]), "why": words})
    if len(shown) < 2:
        return None, left_out
    shown.sort(key=lambda c: (-float(c["estimate"]), str(c["state"])))
    n = len(shown)
    doc = dot(
        [str(c["state"]) for c in shown],
        [
            Series(
                SURVEY_SERIES,
                tuple(100 * float(c["estimate"]) for c in shown),
                tuple(100 * float(c["ci_low"]) for c in shown),
                tuple(100 * float(c["ci_high"]) for c in shown),
                tuple(str(c["precision_flag"]) for c in shown),
            ),
            Series(ASSUMED_SERIES, tuple(rate for _ in range(n))),
        ],
        title=(
            f"Disability (Washington Group cut-off), {group.lower()}: DHS 2024 survey estimates "
            f"with 95% confidence intervals, and an assumed rate of {rate_key(rate)}%, by state"
        ),
        value_label=VALUE_LABEL,
        category_label="State",
        source="Nigeria DHS 2024 (NPC and ICF), Curb Cut estimates; the assumed rate is chosen "
        "on the page",
        unit="percent",
        decimals=1,
        interval_label=INTERVAL_LABEL,
        chart_id=f"sensitivity_{chart_name(age_group, rate).replace('-', '_')}",
    )
    doc["meta"]["places"] = "states"
    doc["meta"]["assumed_rate"] = rate
    return doc, left_out


def dictionary_links(dictionary: ModuleType) -> dict[str, str]:
    anchor = dictionary.slug(STATE_FILE)
    return {
        "file": f"data-dictionary.html#{anchor}",
        "comparison_file": f"data-dictionary.html#{dictionary.slug(COMPARISON_FILE)}",
        **{
            column: f"data-dictionary.html#{dictionary.column_anchor(anchor, column)}"
            for column in DICTIONARY_COLUMNS
        },
    }


def figure_entry(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "label": row["label"],
        "kind": row["kind"],
        "value_percent": row["value_percent"],
        "ci_low_percent": row["ci_low_percent"],
        "ci_high_percent": row["ci_high_percent"],
        "population": row["population"],
        "definition": row["definition"],
        "source": row["source"],
        "source_url": row["source_url"],
    }


def build(data_dir: Path) -> dict[str, dict[str, Any]]:
    """Write the manifest and the chart documents; return the charts by name."""
    explorer = _load("explorer_charts")
    pages = _load("build_state_pages")
    downloads = _load("downloads")
    dictionary = _load("build_data_dictionary")

    marts = dictionary.load_marts(dictionary.DEFAULT_MARTS)
    state_mart = marts["mart_prevalence_state"]
    population_text = state_mart.columns["population_2023"].description
    population_source = next(
        s for s in state_mart.sources if "Demographic Bulletin" in str(s["citation"])
    )
    measure_text = first_sentence_about(state_mart.columns["measure"].description, MEASURE)

    cells = load_cells(data_dir)
    figures = load_figures(data_dir)
    # The page's default (and its <noscript> version) is JONAPWD's own assumed rate.
    if float(figures[ASSUMPTION_ID]["value_percent"]) != DEFAULT_RATE:
        raise ValueError(
            f"DEFAULT_RATE {DEFAULT_RATE} is not JONAPWD's assumed "
            f"{figures[ASSUMPTION_ID]['value_percent']}%"
        )
    flags = {*pages.FLAG_TEXT, "suppressed", "no_data"}
    for age, rows in cells.items():
        unknown = {r["precision_flag"] for r in rows} - flags
        if unknown:
            raise ValueError(f"no label for precision flag {sorted(unknown)} ({age})")

    out_dir = data_dir / "charts" / CHART_DIR
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)
    docs: dict[str, dict[str, Any]] = {}
    charts: dict[str, dict[str, Any]] = {}
    for age, label, _ in AGE_GROUPS:
        for rate in rates():
            doc, left_out = rate_chart(
                age, rate, cells[age], group=label, missing_text=explorer.missing_text
            )
            entry: dict[str, Any] = {"left_out": left_out}
            if doc is not None:
                name = chart_name(age, rate)
                path = out_dir / f"{name}.json"
                path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8", newline="\n")
                docs[f"{CHART_DIR}/{name}"] = doc
                entry["href"] = f"charts/{CHART_DIR}/{name}.json"
            charts[f"{age}|{rate_key(rate)}"] = entry

    manifest = {
        "rates": {"min": RATE_MIN, "max": RATE_MAX, "step": RATE_STEP, "default": DEFAULT_RATE},
        "measure": {
            "code": MEASURE,
            "short": "DISABILITY3",
            "label": explorer.DISABILITY3_LABEL,
            "definition": measure_text,
        },
        "age_groups": [
            {"value": value, "label": label, "short": short} for value, label, short in AGE_GROUPS
        ],
        "assumption": figure_entry(figures[ASSUMPTION_ID]),
        "global": figure_entry(figures[GLOBAL_ID]),
        "population": {
            "description": population_text,
            "source": population_source["citation"],
            "url": population_source["url"],
        },
        "flags": {**pages.FLAG_TEXT, "suppressed": "Suppressed", "no_data": "No data"},
        "missing": explorer.MISSING,
        "states": {age: [survey_cell(c) for c in rows] for age, rows in cells.items()},
        "dictionary": dictionary_links(dictionary),
        "files": {"state": STATE_FILE, "comparison": COMPARISON_FILE},
        "download": {
            "survey": downloads.DHS.survey,
            "year": downloads.DHS.year,
            "sources": [*downloads.DHS.sources, str(population_source["citation"])],
            "terms": f"{downloads.DHS.terms} {population_source['terms']}",
            "values": downloads.VALUES_RULE,
        },
        "charts": charts,
    }
    (data_dir / MANIFEST).write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n"
    )
    return docs
