"""Build the 37 light state pages as plain HTML, with no Plotly and no DuckDB-WASM.

Run after ``export_marts.py``, ``build_charts.py`` and ``build_map.py``, from the repo root:
``uv run python packages/transform/scripts/build_state_pages.py``.

Reads the dbt warehouse read-only (public, disclosure-gated aggregates only) and writes build
artefacts (git-ignored):

* ``site/states/<slug>.html``: one page per state, and ``site/states/index.html`` listing all
  37 with links. Vite takes every ``site/states/*.html`` as an input, so the pages get the
  shared stylesheet and the base path;
* ``site/public/data/charts/states/<slug>.json``: each state's dot plot of the six activities
  (DHS 2024, adults 18+, the state alone; Nigeria is in a table after it), made with
  ``disability_access_charts.dot`` with its findings and audit. The page draws it as a static
  SVG (``dot_svg.py``), names it with the alt-text and shows the library's data table;
* ``site/states/share-images.json``: each page's headline sentence, for the share images
  (``site/scripts/make-share-images.mjs`` screenshots one PNG per state before ``vite build``).

Slugs are the state name in lower case with every run of other characters replaced by one
hyphen (``Akwa Ibom`` -> ``akwa-ibom``, ``Federal Capital Territory`` ->
``federal-capital-territory``); ``site/src/format.js`` (``stateHref``) uses the same rule.

The build fails if any chart document fails its audit, or if the warehouse does not hold
exactly the 37 states.
"""

from __future__ import annotations

import argparse
import html
import importlib.util
import json
import os
import re
import sys
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any

import duckdb
from disability_access_charts import Series, dot

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DB = ROOT / "data" / "curbcut.duckdb"
DEFAULT_PAGES = ROOT / "site" / "states"
DEFAULT_CHARTS = ROOT / "site" / "public" / "data" / "charts" / "states"
# Absolute URLs for the share meta tags (Open Graph needs them). Override with SITE_URL.
DEFAULT_SITE_URL = "https://batestguy.github.io/curb-cut/"
REPO = "https://github.com/batestguy/curb-cut"
REPORT_URL = f"{REPO}/issues/new"
# Each page must load in about a second on a phone (site/tests/states.spec.js checks the
# total); the HTML alone may be at most this many bytes.
HTML_BUDGET = 60 * 1024
MAP_TOLERANCE = 2.0  # coarser than the explorer's map (0.5), to keep each page small

DHS_SOURCE = "Nigeria DHS 2024 (NPC and ICF), Curb Cut estimates"
NATIONAL_LABEL = "Nigeria as a whole"
DOMAINS = (
    ("seeing_3plus", "Seeing"),
    ("hearing_3plus", "Hearing"),
    ("walking_3plus", "Walking or climbing steps"),
    ("cognition_3plus", "Remembering or concentrating"),
    ("selfcare_3plus", "Self-care"),
    ("communication_3plus", "Communicating"),
)
GROUPS = (
    ("18+", "all", "Adults 18+"),
    ("18+", "female", "Women 18+"),
    ("18+", "male", "Men 18+"),
    # An en dash in the ages, as on the main page.
    ("5-17", "all", "Children 5–17"),  # noqa: RUF001
    ("5-17", "female", "Girls 5–17"),  # noqa: RUF001
    ("5-17", "male", "Boys 5–17"),  # noqa: RUF001
)
SECTORS = (("urban", "Urban"), ("rural", "Rural"))
WEALTH = (
    ("lowest", "Poorest fifth"),
    ("second", "Second fifth"),
    ("middle", "Middle fifth"),
    ("fourth", "Fourth fifth"),
    ("highest", "Richest fifth"),
)
# MPI 2021's own items (never DISABILITY3; data/public/aggregates/README.md).
MPI_MEASURES = (
    ("mpi_screener_seeing_any", "Seeing: any difficulty (yes/no question)"),
    ("mpi_screener_hearing_any", "Hearing: any difficulty (yes/no question)"),
    ("mpi_screener_walking_any", "Walking: any difficulty (yes/no question)"),
    ("mpi_selfcare_3plus", "Self-care: a lot of difficulty or cannot do"),
    ("mpi_cognition_3plus", "Remembering or concentrating: a lot of difficulty or cannot do"),
    (
        "mpi_communication_3plus",
        "Communicating (understanding or being understood): a lot of difficulty or cannot do",
    ),
    (
        "mpi_upper_body_3plus",
        "Upper body (lifting a 2-litre bottle or using hands): a lot of difficulty or cannot do",
    ),
)
FLAG_TEXT = {
    "reliable": "Reliable",
    "review": "Review: few events, read with care",
    "unreliable": "Unreliable",
}
TOO_FEW = "not shown: too few respondents"
# Complementary (secondary) suppression: hidden so that a small neighbouring cell cannot be
# worked out by subtraction (D49). precision_reason tells the two kinds apart.
WITHHELD = "not shown: withheld so a neighbouring small cell can't be worked out"
SUPPRESSED_EITHER = (
    "not shown: too few respondents, or withheld to protect a small neighbouring cell"
)
TOO_IMPRECISE = "not shown: too imprecise (unreliable)"
NO_ESTIMATE = "no estimate published"

FAVICON = (
    "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 3 2'%3E%3Cpath "
    "fill='%23008751' d='M0 0h3v2H0z'/%3E%3Cpath fill='%23fff' d='M1 0h1v2H1z'/%3E%3C/svg%3E"
)


def _load(name: str) -> ModuleType:
    """Sibling scripts are not a package; load them by path."""
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(f"{name}.py"))
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


dot_svg = _load("dot_svg")


def state_slug(name: str) -> str:
    """Stable page name: lower case, every run of non-letters replaced by one hyphen."""
    return re.sub(r"[^a-z]+", "-", name.lower()).strip("-")


def in_name(state: str) -> str:
    """The state's name inside a sentence ("in Kano", "in the Federal Capital Territory")."""
    return f"the {state}" if state == "Federal Capital Territory" else state


@dataclass(frozen=True)
class Cell:
    """One published survey cell, as proportions (0-1). Suppressed cells have no numbers."""

    estimate: float | None
    ci_low: float | None
    ci_high: float | None
    flag: str
    suppressed: bool = False
    reason: str | None = None

    @property
    def shown(self) -> bool:
        return not self.suppressed and self.estimate is not None


Key = tuple[str, ...]


@dataclass
class SiteData:
    states: list[dict[str, Any]]
    cells: dict[Key, Cell]  # (state_code, source, measure, age_group, sex)
    national: dict[Key, Cell]  # (source, measure, age_group, sex)
    breakdowns: dict[Key, Cell]  # (level, geography, breakdown, breakdown_level, age_group)


def _cell(row: Mapping[str, Any]) -> Cell:
    suppressed = bool(row["suppressed"])
    return Cell(
        None if suppressed or row["estimate"] is None else float(row["estimate"]),
        None if suppressed or row["ci_low"] is None else float(row["ci_low"]),
        None if suppressed or row["ci_high"] is None else float(row["ci_high"]),
        "suppressed" if suppressed else str(row["precision_flag"]),
        suppressed,
        row.get("precision_reason"),
    )


def _rows(con: duckdb.DuckDBPyConnection, sql: str) -> list[dict[str, Any]]:
    cursor = con.execute(sql)
    columns = [d[0] for d in cursor.description]
    return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]


CELL = "estimate, ci_low, ci_high, precision_flag, precision_reason, suppressed"


def load(con: duckdb.DuckDBPyConnection) -> SiteData:
    """Everything the pages need, from the public marts and seeds."""
    states = _rows(
        con,
        "select state, state_code, zone, capital, population_2023, jonapwd_total "
        "from mart_state_profile order by state",
    )
    if len(states) != 37:
        raise ValueError(f"expected 37 states in mart_state_profile, found {len(states)}")
    by_sex = {
        (r["state"], r["sex"]): r["population_2023"]
        for r in _rows(con, "select state, sex, population_2023 from state_population_by_sex_2023")
    }
    for s in states:
        s["slug"] = state_slug(s["state"])
        s["population_female"] = by_sex.get((s["state"], "female"))
        s["population_male"] = by_sex.get((s["state"], "male"))
    cells = {
        (r["state_code"], r["source"], r["measure"], r["age_group"], r["sex"]): _cell(r)
        for r in _rows(
            con,
            f"select state_code, source, measure, age_group, sex, {CELL} "
            "from mart_prevalence_state where has_data",
        )
    }
    national = {
        (r["source"], r["measure"], r["age_group"], r["sex"]): _cell(r)
        for r in _rows(
            con,
            f"select source, measure, age_group, sex, {CELL} "
            "from mart_prevalence_national_zone where geography_level = 'national'",
        )
    }
    breakdowns = {
        (
            r["geography_level"],
            r["geography"],
            r["breakdown"],
            r["breakdown_level"],
            r["age_group"],
        ): _cell(r)
        for r in _rows(
            con,
            f"select geography_level, geography, breakdown, breakdown_level, age_group, {CELL} "
            "from mart_prevalence_breakdowns where source = 'dhs2024' "
            "and measure = 'disability3' and sex = 'all' "
            "and geography_level in ('state', 'zone') "
            "and breakdown in ('sector', 'wealth_quintile')",
        )
    }
    return SiteData(states, cells, national, breakdowns)


# --- Text -----------------------------------------------------------------------------------


def esc(text: object) -> str:
    return html.escape(str(text), quote=True)


def num1(percent: float) -> str:
    """A percentage to 1 decimal; above 0 but under 0.05 is "<0.1", not a misleading 0.0."""
    return "<0.1" if 0 < percent < 0.05 else f"{percent:.1f}"


def pct(proportion: float) -> str:
    return f"{num1(100 * proportion)}%"


def hidden_text(cell: Cell) -> str:
    """Why a suppressed cell is not shown: too few respondents, or withheld (secondary)."""
    reason = (cell.reason or "").lower()
    if "complementary" in reason:
        return WITHHELD
    if reason.startswith("n<30"):
        return TOO_FEW
    return SUPPRESSED_EITHER


def interval(cell: Cell) -> str:
    assert cell.ci_low is not None and cell.ci_high is not None
    return f"95% confidence interval {pct(cell.ci_low)} to {pct(cell.ci_high)}"


def headline_sentence(state: str, cell: Cell | None, national: Cell | None) -> str:
    """The page's headline, also the share image's text and its alt text."""
    where = in_name(state)
    if cell is None:
        return f"No DHS 2024 disability figure for adults is published for {where}."
    if not cell.shown:
        return (
            f"The DHS 2024 survey has too few respondents in {where} to publish a disability "
            "figure for adults."
        )
    assert cell.estimate is not None
    text = (
        f"In {where}, the DHS 2024 survey estimates that {pct(cell.estimate)} of adults aged 18 "
        f"and over living in households ({interval(cell)}) have a lot of difficulty with, or "
        "cannot do at all, at least one of six everyday activities"
    )
    if national is not None and national.shown and national.estimate is not None:
        text += f"; for Nigeria as a whole the figure is {pct(national.estimate)}"
    text += "."
    if cell.flag == "review":
        text += " Read with care: the estimate rests on few events."
    elif cell.flag == "unreliable":
        text += " The estimate is too imprecise to rely on."
    return text


def figure_text(cell: Cell | None) -> str:
    """ "4.6% (95% confidence interval 3.6% to 5.7%); precision: reliable"."""
    if cell is None:
        return NO_ESTIMATE
    if not cell.shown:
        return hidden_text(cell)
    assert cell.estimate is not None
    flag = FLAG_TEXT.get(cell.flag, cell.flag).lower()
    return f"{pct(cell.estimate)} ({interval(cell)}); precision: {flag}"


# --- HTML pieces ----------------------------------------------------------------------------

# Short headers so most tables fit a phone without scrolling; every caption says what Low
# and High are.
CELL_COLUMNS = ("Estimate (%)", "Low (%)", "High (%)", "Precision")
INTERVAL_NOTE = ". Low and High: the 95% confidence interval."


def cell_tds(cell: Cell | None, *, missing: str = TOO_FEW) -> str:
    """The four value cells of a row; a cell not shown gets one spanning cell saying why.

    Estimates flagged unreliable are not shown (figures appear only where precision passes);
    those flagged for review are shown with their hedge.
    """
    if cell is None:
        return f'<td colspan="4">{esc(missing)}</td>'
    if not cell.shown:
        return f'<td colspan="4">{esc(hidden_text(cell))}</td>'
    if cell.flag == "unreliable":
        return f'<td colspan="4">{TOO_IMPRECISE}</td>'
    assert cell.estimate is not None and cell.ci_low is not None and cell.ci_high is not None
    values = (100 * cell.estimate, 100 * cell.ci_low, 100 * cell.ci_high)
    nums = "".join(f'<td class="num">{esc(num1(v))}</td>' for v in values)
    return f"{nums}<td>{esc(FLAG_TEXT.get(cell.flag, cell.flag))}</td>"


def cell_table(
    caption: str,
    first: str,
    rows: Iterable[tuple[str, Cell | None]],
    *,
    missing: str = TOO_FEW,
) -> str:
    head = f'<th scope="col">{esc(first)}</th>' + "".join(
        f'<th scope="col"{"" if c == "Precision" else ' class="num"'}>{esc(c)}</th>'
        for c in CELL_COLUMNS
    )
    body = "".join(
        f'<tr><th scope="row">{esc(label)}</th>{cell_tds(cell, missing=missing)}</tr>'
        for label, cell in rows
    )
    table = (
        f"<table><caption>{esc(caption + INTERVAL_NOTE)}</caption>"
        f"<thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"
    )
    return wide_table(table, caption)


def doc_table(doc: Mapping[str, Any]) -> str:
    """The chart document's own table (caption, columns, rows) laid out as the library's
    ``to_html`` does, except that estimates above 0 but under 0.05 are written "<0.1"."""
    table = doc["table"]
    columns = table["columns"]

    def cls(column: Mapping[str, Any]) -> str:
        return "" if column.get("type", "text") == "text" else ' class="num"'

    def text(value: Any, column: Mapping[str, Any]) -> str:
        if value is None:
            return ""
        if column.get("type") == "number":
            if column["key"].endswith("value"):
                return num1(value)
            return f"{value:,.{int(column.get('decimals', 1))}f}"
        return str(value)

    head = "".join(f'<th scope="col"{cls(c)}>{esc(c["label"])}</th>' for c in columns)
    rows = []
    for row in table["rows"]:
        cells = [
            f'<th scope="row">{esc(text(v, c))}</th>'
            if i == 0
            else f"<td{cls(c)}>{esc(text(v, c))}</td>"
            for i, (v, c) in enumerate(zip(row, columns, strict=True))
        ]
        rows.append(f"<tr>{''.join(cells)}</tr>")
    return (
        f"<table><caption>{esc(table['caption'])}</caption><thead><tr>{head}</tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )


def wide_table(table_html: str, caption: str) -> str:
    """Every table sits in a named, focusable region, so it can be scrolled sideways from the
    keyboard wherever it does not fit (a phone, or high zoom). No script needed."""
    label = esc(f"{caption} (table, may scroll sideways)")
    return (
        f'<div class="table-wrap" role="region" tabindex="0" aria-label="{label}">'
        f"{table_html}</div>"
    )


def findings_html(doc: Mapping[str, Any]) -> str:
    """The library's statistical findings, laid out as on the main page (prevalence.js)."""
    findings = doc.get("findings")
    if not findings:
        return ""
    lines = findings["lines"]
    items = "".join(f"<li>{esc(s['text'])}</li>" for s in findings["statements"])
    statements = (
        f'<ul class="findings-list sentences" aria-labelledby="domains-findings-heading">'
        f"{items}</ul>"
        if items
        else ""
    )
    notes = "".join(
        f"<p>{esc(t)}</p>"
        for t in (lines.get("none"), lines.get("dropped"), lines.get("withheld"))
        if t
    )
    families = "".join(
        f"<li>{esc(f['label'])}: {f['checked']} checked, {f['supported']} supported"
        f"{f', {f["dropped"]} not tested' if f['dropped'] else ''}.</li>"
        for f in findings["families"]
        if f["checked"] + f["dropped"] > 0
    )
    caveats = [c["text"] for c in findings["caveats"] if c["id"] != "descriptive"]
    method = " ".join([lines["method"], *caveats, f"Source: {doc['meta']['source']}."])
    return (
        '<div class="findings">'
        '<h4 id="domains-findings-heading">Which differences the survey can show</h4>'
        "<p>We checked a fixed set of comparisons between this state's six activities, set "
        "by a rule fixed in advance: the highest and lowest against the next, and neighbours "
        "in the ranking. A difference "
        "counts as supported only if it is larger than the survey's uncertainty allows, after "
        "allowing for how many comparisons were made. These are descriptions, not causes.</p>"
        f'<p class="findings-count"><strong>{esc(lines["count"])}</strong></p>'
        f"{statements}{notes}"
        '<details class="more"><summary>What was compared, and how</summary>'
        f'<ul class="sentences">{families}</ul><p>{esc(method)}</p></details>'
        "</div>"
    )


def chart_html(doc: Mapping[str, Any], national_table: str = "") -> str:
    title = doc["title"]
    caption = doc["table"]["caption"]
    return (
        '<figure class="chart-figure dot-chart" aria-labelledby="domains-chart-title">'
        f"{dot_svg.legend_html(doc)}"
        '<div class="chart dot-holder" role="img" aria-labelledby="domains-chart-desc">'
        f"{dot_svg.render_dot_svg(doc)}</div>"
        "<figcaption>"
        f'<span id="domains-chart-title" class="chart-title">{esc(title)}</span>'
        f'<span id="domains-chart-desc" class="chart-desc" aria-hidden="true">'
        f"{esc(doc['alt_text'])}</span>"
        "</figcaption></figure>"
        f"{findings_html(doc)}"
        '<p class="table-intro">The same figures as a table:</p>'
        f"{wide_table(doc_table(doc), caption)}"
        f"{national_table}"
    )


def locator_html(state: Mapping[str, Any], geo: Mapping[str, Any]) -> str:
    """The state on a map of Nigeria: filled and outlined (not colour alone), small states
    ringed. One image with a short name; the drawing itself is hidden."""
    code = state["state_code"]
    others = "".join(d for c, d in geo["paths"].items() if c != code)
    ring = geo["rings"].get(code)
    ring_svg = (
        f'<circle class="locator-ring" cx="{ring[0]}" cy="{ring[1]}" r="{ring[2]}"/>'
        if ring
        else ""
    )
    name = (
        f"Map of Nigeria with {in_name(state['state'])} highlighted, in the {state['zone']} zone."
    )
    return (
        '<figure class="locator locator-static">'
        f'<div class="locator-map" role="img" aria-label="{esc(name)}">'
        f'<svg viewBox="{esc(geo["viewBox"])}" aria-hidden="true" focusable="false">'
        f'<path d="{others}"/><path class="selected" d="{geo["paths"][code]}"/>{ring_svg}'
        "</svg></div>"
        "<figcaption>Boundaries: geoBoundaries (CC BY 4.0)</figcaption></figure>"
    )


LAW_HTML = """<section aria-labelledby="law-heading">
<h2 id="law-heading">The law: national facts</h2>
<p>These national facts apply in every state. This page does not cover state laws.</p>
<ul class="sentences">
<li>The Discrimination against Persons with Disabilities (Prohibition) Act, 2018 (Act No. 2)
commenced on 17 January 2019 (<cite>Official Gazette</cite> No. 10, Vol. 106).</li>
<li>Section 6 gave a transition period of five years from commencement, to January 2024,
within which public buildings and structures that were inaccessible to persons with
disabilities were to be modified to be accessible.</li>
<li>Section 29 says employers in public organisations shall, "as much as possible", have
persons with disabilities make up at least 5% of their employment. It covers public
organisations only.</li>
<li>Section 31 establishes the National Commission for Persons with Disabilities.</li>
<li>Nigeria signed the UN Convention on the Rights of Persons with Disabilities on 30 March
2007 and ratified it on 24 September 2010.</li>
</ul>
<p class="card-sources">Sources: the Act as gazetted,
<a href="https://ncpwd.gov.ng/pdfs/6document.pdf">copy hosted by the National Commission for
Persons with Disabilities</a>; the
<a href="https://treaties.un.org/Pages/ViewDetails.aspx?src=TREATY&amp;mtdsg_no=IV-15&amp;chapter=4&amp;clang=_en">UN
Treaty Collection</a>, chapter IV-15.</p>
</section>"""


def header_html(crumb: str) -> str:
    return (
        '<a class="skip-link" href="#main">Skip to main content</a>'
        '<div class="flag-band" aria-hidden="true"></div>'
        '<header class="site-header"><p class="site-name"><a href="../">Curb Cut</a></p>'
        f'<nav class="breadcrumb" aria-label="Breadcrumb"><ol>{crumb}</ol></nav></header>'
    )


FOOTER_HTML = f"""<footer class="site-footer">
<h2 class="footer-heading">Accessibility and feedback</h2>
<p>This site has automated accessibility tests (axe, keyboard); it has not yet been tested
by a regular screen-reader user. If anything is hard to use or looks wrong,
<a href="{REPORT_URL}">report a problem on GitHub</a>.</p>
<p><a href="../methodology.html">Methodology: definitions, sources and limits</a>.
<a href="../">Back to the main page</a>. Source code and data notes:
<a href="{REPO}">github.com/batestguy/curb-cut</a>.</p>
</footer>"""


def head_html(
    *,
    title: str,
    description: str,
    canonical: str,
    image: str | None = None,
    image_alt: str | None = None,
    extra_css: str = "",
) -> str:
    share = ""
    if image and image_alt:
        share = (
            f'<meta property="og:image" content="{esc(image)}" />'
            '<meta property="og:image:width" content="1200" />'
            '<meta property="og:image:height" content="630" />'
            f'<meta property="og:image:alt" content="{esc(image_alt)}" />'
            '<meta name="twitter:card" content="summary_large_image" />'
        )
    style = f"<style>{extra_css}</style>" if extra_css else ""
    return (
        '<!doctype html>\n<html lang="en-NG">\n<head>\n<meta charset="utf-8" />\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1" />\n'
        '<meta name="color-scheme" content="light dark" />\n'
        f"<title>{esc(title)}</title>\n"
        f'<meta name="description" content="{esc(description)}" />\n'
        f'<link rel="canonical" href="{esc(canonical)}" />\n'
        '<meta property="og:type" content="website" />'
        '<meta property="og:site_name" content="Curb Cut" />'
        f'<meta property="og:title" content="{esc(title)}" />'
        f'<meta property="og:description" content="{esc(description)}" />'
        f'<meta property="og:url" content="{esc(canonical)}" />{share}\n'
        f'<link rel="icon" type="image/svg+xml" href="{FAVICON}" />\n'
        '<link rel="stylesheet" href="../src/style.css" />\n'
        f"{style}</head>\n"
    )


# --- The page -------------------------------------------------------------------------------


@dataclass
class Page:
    slug: str
    state: str
    sentence: str
    html: str
    chart: dict[str, Any] | None


def domain_chart(state: Mapping[str, Any], data: SiteData) -> dict[str, Any] | None:
    """The six activities at the cut-off, adults 18+, for the state alone.

    One series, so the findings and the alt-text compare only this state's activities
    (``disability_access_charts`` has no per-category reference, so a second "Nigeria as a
    whole" series would bring Nigeria's own rankings into both). Nigeria's figures are in a
    table after the chart. Activities without a published state cell are left out and named
    as withheld. Fewer than two activities: no chart (the page says why).
    """
    code, name = state["state_code"], state["state"]
    shown: list[tuple[str, Cell]] = []
    withheld: list[str] = []
    for measure, label in DOMAINS:
        cell = data.cells.get((code, "dhs2024", measure, "18+", "all"))
        if cell is None or not cell.shown:
            withheld.append(label)
            continue
        shown.append((label, cell))
    if len(shown) < 2:
        return None
    shown.sort(key=lambda r: -(r[1].estimate or 0.0))  # stable: ties keep DOMAINS order
    cells = [r[1] for r in shown]
    return dot(
        [r[0] for r in shown],
        [
            Series(
                name,
                tuple(100 * (c.estimate or 0.0) for c in cells),
                tuple(100 * (c.ci_low or 0.0) for c in cells),
                tuple(100 * (c.ci_high or 0.0) for c in cells),
                tuple(c.flag for c in cells),
            )
        ],
        title=(
            f"Adults 18+ in {in_name(name)} with a lot of difficulty or who cannot do it at all, "
            "by activity, with 95% confidence intervals"
        ),
        value_label="Adults (%)",
        category_label="Activity",
        source=DHS_SOURCE,
        unit="percent",
        decimals=1,
        chart_id=f"state_domains_{state['slug'].replace('-', '_')}",
        findings=True,
        withheld=withheld,
    )


def dhs_section(
    state: Mapping[str, Any], data: SiteData, sentence: str, chart: dict[str, Any] | None
) -> str:
    code, name, zone = state["state_code"], state["state"], state["zone"]
    where = in_name(name)
    headline = data.cells.get((code, "dhs2024", "disability3", "18+", "all"))
    national = data.national.get(("dhs2024", "disability3", "18+", "all"))
    groups = [
        (label, data.cells.get((code, "dhs2024", "disability3", age, sex)))
        for age, sex, label in GROUPS
    ]
    sectors = [
        (label, data.breakdowns.get(("state", code, "sector", level, "18+")))
        for level, label in SECTORS
    ]
    zone_wealth = [
        (label, data.breakdowns.get(("zone", zone, "wealth_quintile", level, "18+")))
        for level, label in WEALTH
    ]
    state_wealth = [
        (label, data.breakdowns.get(("state", code, "wealth_quintile", level, "18+")))
        for level, label in WEALTH
    ]
    national_domains = cell_table(
        f"{NATIONAL_LABEL}: adults 18+ by activity, DHS 2024, for comparison",
        "Activity",
        [(label, data.national.get(("dhs2024", m, "18+", "all"))) for m, label in DOMAINS],
        missing=NO_ESTIMATE,
    )
    national_part = (
        '<p class="table-intro">For comparison, the same activities for Nigeria as a whole. '
        "The findings above do not compare the state with Nigeria.</p>"
        f"{national_domains}"
    )
    if chart is not None:
        chart_part = chart_html(chart, national_part)
    else:
        chart_part = (
            "<p>The activity chart is not shown: fewer than two of the six activities have a "
            f"published estimate for {esc(where)}.</p>"
        )
    flag_link = '<a href="../methodology.html#precision-heading">what the precision flags mean</a>'
    return f"""<section aria-labelledby="dhs-heading">
<h2 id="dhs-heading">Measured disability: the DHS 2024 survey</h2>
<p class="lead" id="headline">{esc(sentence)}</p>
<dl class="facts compare">
<dt>Adults 18+ with disability in {esc(where)}</dt><dd>{esc(figure_text(headline))}</dd>
<dt>{NATIONAL_LABEL}, for comparison</dt><dd>{esc(figure_text(national))}</dd>
</dl>
<p>The figures use the Washington Group's disability cut-off: "a lot of difficulty" or
"cannot do at all" in at least one of six everyday activities. Every estimate comes with its
95% confidence interval and a precision flag (see {flag_link}). Where two intervals overlap a
lot, the survey cannot tell the figures apart.</p>
<h3 id="groups-heading">Women and men, adults and children</h3>
{
        cell_table(
            f"Disability in {where} by sex and age, DHS 2024",
            "Group",
            groups,
            missing=NO_ESTIMATE,
        )
    }
<p>Shown only where the precision flag allows: estimates flagged unreliable are left out.
Children's figures are often flagged for review: disability is rarer among children, so each
state has few children with a difficulty in the sample.</p>
<h3 id="domains-heading">The six activities</h3>
{chart_part}
<h3 id="sector-heading">Urban and rural areas</h3>
<p>Adults 18+. Shown only where the precision flag allows: estimates flagged unreliable are left
out.</p>
{
        cell_table(
            f"Disability among adults in {where}, urban and rural, DHS 2024",
            "Area",
            sectors,
        )
    }
<h3 id="wealth-heading">Household wealth</h3>
<p>Within one state, the survey has few adults with a disability in each wealth group, so most
state figures by wealth are imprecise and some are not shown for privacy. This table shows the
{esc(zone)} zone, which includes {esc(where)}. Wealth groups are fifths of all households in
Nigeria, ranked by the DHS wealth index (household assets).</p>
{
        cell_table(
            f"Disability among adults in the {zone} zone by household wealth, DHS 2024",
            "Wealth group",
            zone_wealth,
        )
    }
<details class="more">
<summary>{esc(name)}'s own figures by wealth</summary>
<p>Read with care. Cells with too few respondents are not shown, and so is one more cell
wherever it could otherwise be worked out by subtraction.</p>
{
        cell_table(
            f"Disability among adults in {where} by household wealth, DHS 2024",
            "Wealth group",
            state_wealth,
        )
    }
</details>
</section>"""


def mpi_section(state: Mapping[str, Any], data: SiteData) -> str:
    code, where = state["state_code"], in_name(state["state"])
    rows = [
        (label, data.cells.get((code, "mpi2021", measure, "18+", "all")))
        for measure, label in MPI_MEASURES
    ]
    rows = [(label, cell) for label, cell in rows if cell is not None]
    if rows:
        table = cell_table(
            f"MPI 2021: adults 18+ in {where}, by MPI's own disability questions",
            "MPI question",
            rows,
        )
    else:
        table = f"<p>No MPI 2021 disability figures are published for {esc(where)}.</p>"
    return f"""<section aria-labelledby="mpi-heading">
<h2 id="mpi-heading">A different measure: the MPI 2021 survey</h2>
<p>The National Bureau of Statistics' Multidimensional Poverty Index survey 2021 asked its own
disability questions, which are not the Washington Group questions used above. Seeing, hearing
and walking were yes/no questions, so they count any difficulty, not only a lot of difficulty.
So these figures measure something different: they are not comparable with the DHS 2024
figures, and they are not added up into one disability rate.</p>
{table}
</section>"""


def page_html(state: Mapping[str, Any], data: SiteData, geo: Mapping[str, Any], site_url: str):
    name, slug = state["state"], state["slug"]
    where = in_name(name)
    headline = data.cells.get((state["state_code"], "dhs2024", "disability3", "18+", "all"))
    national = data.national.get(("dhs2024", "disability3", "18+", "all"))
    sentence = headline_sentence(name, headline, national)
    chart = domain_chart(state, data)
    title = f"Disability in {where}: Curb Cut"
    description = (
        f"Disability in {where} from the DHS 2024 survey, with intervals: by sex, age, activity, "
        "urban and rural areas and wealth; with MPI 2021, JONAPWD's assumed figure, population "
        "and Nigeria's disability law."
    )
    url = f"{site_url}states/{slug}.html"
    head = head_html(
        title=title,
        description=description,
        canonical=url,
        image=f"{site_url}share/{slug}.png",
        image_alt=sentence,
        extra_css=dot_svg.theme_css(chart) if chart else "",
    )
    crumb = (
        '<li><a href="../">Curb Cut</a></li><li><a href="./">State pages</a></li>'
        f'<li aria-current="page">{esc(name)}</li>'
    )

    def num(v: int | None) -> str:
        return "not available" if v is None else f"{int(v):,}"

    jonapwd = state.get("jonapwd_total")
    jonapwd_text = (
        f"JONAPWD's 2025 figure for {esc(where)}: <strong>{num(jonapwd)}</strong> people with "
        "disabilities, assumed rather than counted."
        if jonapwd is not None
        else f"JONAPWD publishes no figure for {esc(where)}."
    )
    body = f"""<body>
{header_html(crumb)}
<main id="main" tabindex="-1" class="state-page">
<h1>Disability in {esc(where)}</h1>
{dhs_section(state, data, sentence, chart)}
<section aria-labelledby="about-heading">
<h2 id="about-heading">About {esc(where)}</h2>
<div class="state-card-body">
<dl class="facts">
<dt>Geopolitical zone</dt><dd>{esc(state["zone"])}</dd>
<dt>Capital</dt><dd>{esc(state["capital"])}</dd>
<dt>Population, 2023 projection</dt><dd>{num(state["population_2023"])}</dd>
<dt>Women and girls</dt><dd>{num(state.get("population_female"))}</dd>
<dt>Men and boys</dt><dd>{num(state.get("population_male"))}</dd>
</dl>
{locator_html(state, geo)}
</div>
<p class="card-sources">Sources: population, National Bureau of Statistics,
<a href="https://microdata.nigerianstat.gov.ng/index.php/catalog/182">Demographic Bulletin 2023</a>,
Annex 3 (source: National Population Commission); capital and zone,
<a href="https://en.wikipedia.org/wiki/States_of_Nigeria">Wikipedia</a>.</p>
</section>
{mpi_section(state, data)}
<section aria-labelledby="jonapwd-heading">
<h2 id="jonapwd-heading">Assumed, not counted: JONAPWD's 2025 figure</h2>
<div class="caveat">
<h3 id="caveat-heading">This is an estimate built on an assumption</h3>
<p>No one was counted. JONAPWD applied the global 15% disability rate to 2025 population
projections. Totals may differ from JONAPWD's by a few people (rounding).</p>
</div>
<p>{jonapwd_text}</p>
</section>
{LAW_HTML}
<section aria-labelledby="sources-heading">
<h2 id="sources-heading">Sources and methods</h2>
<ul class="sentences">
<li>Measured figures: The DHS Program, <cite>Nigeria Demographic and Health Survey 2024</cite>
(National Population Commission and ICF), Washington Group Short Set; estimates by Curb Cut
from the survey microdata, used for the registered project "Curb Cut: disability prevalence
and poverty in Nigeria". Only disclosure-checked aggregates are published.</li>
<li>MPI figures: National Bureau of Statistics, Multidimensional Poverty Index Survey 2021;
estimates by Curb Cut, aggregated reporting only.</li>
<li>Assumed figures: Joint National Association of Persons with Disabilities (JONAPWD),
<a href="https://jonapwdng.org/10865-2/"><cite>2025 Assumptive Disability Disaggregated
Data</cite></a>. © JONAPWD, all rights reserved; figures are cited, the PDF is not
redistributed.</li>
<li>Boundaries: <a href="https://www.geoboundaries.org/">geoBoundaries</a> (CC BY 4.0; source
GRID3).</li>
</ul>
<p><a href="../methodology.html">How the figures were made: definitions, sources and limits</a>.
The published survey aggregates are
<a href="{REPO}/tree/main/data/public/aggregates">on GitHub</a>.</p>
</section>
</main>
{FOOTER_HTML}
</body>
</html>
"""
    return Page(slug, name, sentence, head + body, chart)


def index_html(pages: Sequence[Page], site_url: str) -> str:
    items = "".join(
        f'<li><a href="./{p.slug}.html">{esc(p.state)}</a></li>'
        for p in sorted(pages, key=lambda p: p.state)
    )
    head = head_html(
        title="State pages: Curb Cut",
        description=(
            "One page for each of Nigeria's 36 states and the Federal Capital Territory, with "
            "measured disability from the DHS 2024 survey and other public sources."
        ),
        canonical=f"{site_url}states/",
    )
    crumb = '<li><a href="../">Curb Cut</a></li><li aria-current="page">State pages</li>'
    return f"""{head}<body>
{header_html(crumb)}
<main id="main" tabindex="-1">
<h1>State pages</h1>
<p>Each page brings together the public figures for one state: measured disability from the DHS
2024 survey with intervals, MPI 2021's own measure, JONAPWD's assumed figure, population and
Nigeria's disability law.</p>
<section aria-labelledby="all-states-heading">
<h2 id="all-states-heading">All {len(pages)} states, by name</h2>
<ul class="state-list state-links">{items}</ul>
</section>
</main>
{FOOTER_HTML}
</body>
</html>
"""


def build(
    data: SiteData, geo: Mapping[str, Any], pages_dir: Path, charts_dir: Path, site_url: str
) -> list[Page]:
    """Write every page, its chart document, the index and the share-image list."""
    if not site_url.endswith("/"):
        site_url += "/"
    pages = [page_html(s, data, geo, site_url) for s in data.states]
    slugs = [p.slug for p in pages]
    if len(set(slugs)) != len(slugs):
        raise ValueError(f"state slugs are not unique: {slugs}")
    heavy = [p.slug for p in pages if len(p.html.encode("utf-8")) > HTML_BUDGET]
    if heavy:
        raise ValueError(f"over the {HTML_BUDGET:,}-byte page budget: {', '.join(heavy)}")
    failed = [p.slug for p in pages if p.chart is not None and not p.chart["audit"]["passed"]]
    if failed:
        raise ValueError(f"chart audit failed for: {', '.join(failed)}")
    for folder, pattern in ((pages_dir, "*.html"), (charts_dir, "*.json")):
        folder.mkdir(parents=True, exist_ok=True)
        for stale in folder.glob(pattern):
            stale.unlink()
    for p in pages:
        (pages_dir / f"{p.slug}.html").write_text(p.html, encoding="utf-8", newline="\n")
        if p.chart is not None:
            (charts_dir / f"{p.slug}.json").write_text(
                json.dumps(p.chart, indent=2) + "\n", encoding="utf-8", newline="\n"
            )
    (pages_dir / "index.html").write_text(
        index_html(pages, site_url), encoding="utf-8", newline="\n"
    )
    share = [{"slug": p.slug, "state": p.state, "sentence": p.sentence} for p in pages]
    (pages_dir / "share-images.json").write_text(
        json.dumps(share, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n"
    )
    return pages


def locator_geo() -> dict[str, Any]:
    build_map = _load("build_map")
    geojson = json.loads(build_map.DEFAULT_GEOJSON.read_text(encoding="utf-8"))
    return build_map.build(geojson, build_map.SEEDS, tolerance=MAP_TOLERANCE)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the 37 state pages.")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--pages-dir", type=Path, default=DEFAULT_PAGES)
    parser.add_argument("--charts-dir", type=Path, default=DEFAULT_CHARTS)
    parser.add_argument("--site-url", default=os.environ.get("SITE_URL", DEFAULT_SITE_URL))
    args = parser.parse_args(argv)
    try:
        with duckdb.connect(str(args.db), read_only=True) as con:
            data = load(con)
        pages = build(data, locator_geo(), args.pages_dir, args.charts_dir, args.site_url)
    except ValueError as error:
        print(f"State pages failed: {error}", file=sys.stderr)
        return 1
    charts = sum(p.chart is not None for p in pages)
    largest = max(len(p.html.encode("utf-8")) for p in pages)
    made = (
        f"{charts} chart documents (audits passed)"
        if charts
        else "no chart documents (fewer than two activities published, as in the fixtures)"
    )
    print(
        f"wrote {len(pages)} state pages, the index and {made}; largest page {largest:,} "
        f"bytes; to {args.pages_dir}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
