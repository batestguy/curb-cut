"""Build ``site/poverty.html``, the P5 results page, as plain HTML with no script.

Run after ``export_marts.py`` and ``build_charts.py``, from the repo root:
``uv run python packages/transform/scripts/build_poverty_page.py``.

Reads ``site/public/data/poverty.json`` (disclosure-gated P5 estimates, exported from the
warehouse) and the two chart documents ``poverty_headline.json`` and
``poverty_dimensions.json`` (made by ``disability_access_charts.dot`` in
``build_charts.py``), and writes ``site/poverty.html`` (git-ignored; Vite takes it as an
input), and every table's CSV and JSON download to ``site/public/data/downloads/poverty/``
(``downloads.py``, from the same cells the table shows). Every number on the page comes
from those files: each is wrapped in a span naming
its path in ``poverty.json`` (``poverty_text.Numbers``), which ``site/tests/
poverty.spec.js`` checks. The charts are drawn as static SVG (``dot_svg.py``), named by the
library's alt-text and followed by the library's data table.

The build fails if a chart audit fails, a needed estimate is missing or suppressed, or the
page uses wording the pre-registration rules out (``poverty_text.forbidden``).
"""

from __future__ import annotations

import argparse
import html
import importlib.util
import json
import os
import re
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DATA = ROOT / "site" / "public" / "data"
DEFAULT_PAGE = ROOT / "site" / "poverty.html"
BRIEF_PDF = "downloads/p5-poverty-brief.pdf"
BRIEF_MD = "docs/brief/p5-poverty-brief.md"


def _load(name: str) -> ModuleType:
    """Sibling scripts are not a package; load them by path."""
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(f"{name}.py"))
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


pages = _load("build_state_pages")
dot_svg = _load("dot_svg")
text = _load("poverty_text")
downloads = _load("downloads")

esc = pages.esc
REPO = pages.REPO
REPORT_URL = pages.REPORT_URL
REPORT_HTML = pages.REPORT_HTML
# The page links its downloads (data/downloads/poverty/<table-id>.csv and .json).
DOWNLOADS_HREF = "./data/downloads/"


@dataclass
class PageDownloads(downloads.Collector):
    """The page's downloads, with the numbers the tables' spans name."""

    nums: Any = None


SECONDARY_ROWS = (
    "s1_score",
    "s2_broad",
    "s3_head",
    "s4_health",
    "s4_education",
    "s4_living_standards",
    "s4_work_and_shocks",
    "s5_unasked_severe",
    "s6_routing_free",
)
HOLM = ("s1_score", "s2_broad", "s3_head")
ROBUSTNESS_ROWS = (
    "rob_no_head_education",
    "rob_place_head_sex_age",
    "rob_state_only_place",
    "rob_learners_logistic",
    "rob_learners_forest",
    "rob_learners_boosting",
    "rob_outcome_poor_fuel_alt",
    "rob_outcome_poor_shock_dk0",
)
BENCHMARKS = (
    ("head_education", "the household head's education"),
    ("place", "place (state and senatorial district together)"),
    ("sector", "living in an urban or a rural area"),
)
LEARNERS = (
    ("logistic", "Logistic regression"),
    ("forest", "Random forest"),
    ("boosting", "Gradient boosting"),
)


NUMBER_SPAN = re.compile(
    r'<span class="n" data-key="([^"]*)" data-factor="([^"]*)" data-decimals="(\d+)" '
    r'data-format="(\w+)">(.*?)</span>'
)


def cell_values(nums: Any, cell: str) -> list[Any]:
    """The values behind one table cell, for its download: a number span gives its value in
    poverty.json times its factor (not rounded for display), two spans joined by "to" (a
    range) give two values, and any other cell gives its text."""
    spans = list(NUMBER_SPAN.finditer(cell))
    if all(m.group(4) == "text" for m in spans):  # words, perhaps with a label span inside
        return [html.unescape(NUMBER_SPAN.sub(lambda m: m.group(5), cell))]
    values = []
    for m in spans:
        key, factor, _, kind, _ = m.groups()
        raw = nums.raw(html.unescape(key))
        if kind == "text":
            values.append(str(raw))
        elif kind == "fixed":
            values.append(float(factor) * float(raw))
        else:  # "int" and "p": the value as exported
            values.append(raw)
    rest = NUMBER_SPAN.sub("", cell)
    if len(spans) == 1 and rest == "":
        return values
    if len(spans) == 2 and rest == " to ":
        return values
    raise ValueError(f"cannot read the value of a table cell: {cell!r}")


def table_download(
    nums: Any,
    caption: str,
    columns: Sequence[str],
    rows: Sequence[Sequence[str]],
    *,
    table_id: str,
    name: str,
    provenance: Any,
    unit: str | None,
) -> Any:
    """The download of a table built by :func:`table`, from the same cells. A column whose
    cells are ranges ("1.2 to 3.4") becomes two columns, ", lower" and ", upper"."""
    values = [[cell_values(nums, c) for c in row] for row in rows]
    out_columns = []
    for j, label in enumerate(columns):
        cells = [row[j] for row in values]
        spans = [m for row in rows for m in NUMBER_SPAN.finditer(row[j])]
        kinds = {m.group(4) for m in spans}
        decimals = int(spans[0].group(3)) if spans else None
        if kinds <= {"text"}:
            column = downloads.Column(label)
        elif kinds == {"int"}:
            column = downloads.Column(label, "integer", 0, unit=None)
        else:
            column = downloads.Column(label, "number", decimals, unit if j > 0 else None)
        if any(len(c) == 2 for c in cells):
            if not all(len(c) == 2 for c in cells):
                raise ValueError(f"{table_id}: column {label!r} mixes ranges and single cells")
            out_columns += [
                downloads.Column(f"{label}, lower", column.type, column.decimals, column.unit),
                downloads.Column(f"{label}, upper", column.type, column.decimals, column.unit),
            ]
        else:
            out_columns.append(column)
    return downloads.TableData(
        table_id,
        name,
        caption,
        tuple(out_columns),
        tuple(tuple(v for cell in row for v in cell) for row in values),
        provenance,
    )


def table(
    caption: str,
    columns: Sequence[str],
    rows: Sequence[Sequence[str]],
    *,
    dl: Any,
    table_id: str,
    name: str,
    provenance: Any = None,
    unit: str | None = None,
    numeric: Sequence[bool] | None = None,
) -> str:
    """A captioned table (first cell of each row is its header) in a scrollable region, then
    its download line (``dl``: the page's ``downloads.Collector``, whose ``nums`` reads the
    values behind the number spans). Cells are HTML already (they may hold number spans)."""
    data = table_download(
        dl.nums,
        caption,
        columns,
        rows,
        table_id=table_id,
        name=name,
        provenance=provenance or downloads.P5_MPI,
        unit=unit,
    )
    numeric = numeric or [False] + [True] * (len(columns) - 1)
    head = "".join(
        f'<th scope="col"{' class="num"' if numeric[i] else ""}>{esc(c)}</th>'
        for i, c in enumerate(columns)
    )
    body = "".join(
        "<tr>"
        + "".join(
            f'<th scope="row">{cell}</th>'
            if i == 0
            else f"<td{' class="num"' if numeric[i] else ''}>{cell}</td>"
            for i, cell in enumerate(row)
        )
        + "</tr>"
        for row in rows
    )
    return pages.wide_table(
        f"<table><caption>{esc(caption)}</caption><thead><tr>{head}</tr></thead>"
        f"<tbody>{body}</tbody></table>",
        caption,
    ) + dl.add(data)


def figure(doc: Mapping[str, Any], key: str, intro: str, dl: Any, table_id: str, name: str) -> str:
    """A library dot plot: static SVG named by the alt-text, then the library's table and its
    download (from the same table)."""
    if not doc["audit"]["passed"]:
        raise ValueError(f"chart {doc['id']} failed its audit")
    data = downloads.from_spec(doc["table"], table_id, name, downloads.P5_MPI)
    return (
        f'<figure class="chart-figure dot-chart" aria-labelledby="{key}-title">'
        f'<div class="chart dot-holder" role="img" aria-labelledby="{key}-desc">'
        f"{dot_svg.render_dot_svg(doc)}</div>"
        "<figcaption>"
        f'<span id="{key}-title" class="chart-title">{esc(doc["title"])}</span>'
        f'<span id="{key}-desc" class="chart-desc" aria-hidden="true">'
        f"{esc(doc['alt_text'])}</span>"
        "</figcaption></figure>"
        f'<p class="table-intro">{intro}</p>'
        f'<div class="chart-table" data-chart="{esc(doc["id"])}">'
        f"{pages.wide_table(pages.doc_table(doc), doc['table']['caption'])}{dl.add(data)}</div>"
    )


def est_cells(nums: Any, eid: str, decimals: int = 1) -> list[str]:
    if nums.raw(f"estimates.{eid}.suppressed"):
        return ["not shown: too few households", "", ""]
    return [nums.est(eid, decimals=decimals), *nums.ci(eid, decimals).split(" to ")]


def result_box(nums: Any, eid: str, heading: str, body: str) -> str:
    return (
        '<div class="p5-result">'
        f"<h3>{esc(heading)}</h3>"
        f'<p class="p5-big">+{nums.est(eid)} percentage points</p>'
        f"<p>95% confidence interval {nums.ci(eid)} points. {nums.count(f'estimates.{eid}.n')} "
        f"households, {nums.count(f'estimates.{eid}.n_exposed')} of them with such a "
        "member.</p>"
        f"<p>{body}</p></div>"
    )


def signed_box(nums: Any, eid: str, heading: str, body: str) -> str:
    """As :func:`result_box`, with the sign written only for a positive estimate."""
    box = result_box(nums, eid, heading, body)
    if nums.raw(f"estimates.{eid}.estimate") < 0:
        box = box.replace('<p class="p5-big">+', '<p class="p5-big">', 1)
    return box


QUANTILES = ("q01", "q05", "q25", "q50", "q75", "q95", "q99")


def quantile_table(nums: Any, dl: Any) -> str:
    """Section 5.1: the cross-fitted propensity's quantiles, exposed and unexposed."""
    rows = [
        [
            esc(f"{int(key[1:])}% of households below"),
            nums.num(f"summary.mpi.quantile_exposed_{key}.value", 1, 3),
            nums.num(f"summary.mpi.quantile_unexposed_{key}.value", 1, 3),
        ]
        for key in QUANTILES
    ]
    return table(
        "The model's estimated chance that a household has a member with a severe difficulty "
        "(propensity, averaged over the repetitions, before the 0.01 cut-off), by group",
        ["Quantile", "With such a member", "Without"],
        rows,
        dl=dl,
        table_id="propensity-quantiles",
        name="the estimated chance of having such a member, by group",
    )


def result_section(nums: Any, charts: Mapping[str, Mapping[str, Any]], dl: Any) -> str:
    quantiles = quantile_table(nums, dl)
    reasons = "".join(f"<li>{r}</li>" for r in text.reasons(nums, "#sensitivity-heading"))
    overlap = (
        "Few households have a member with a severe difficulty: "
        f"{nums.count('estimates.primary.n_exposed')} of "
        f"{nums.count('estimates.primary.n')} in the analysis. So for most households, the "
        "model's estimated chance of having such a member was below 1 in 100, the cut-off "
        "fixed in the pre-registration (0.01). That was the case for "
        f"{nums.share('outside_weighted_share')} of people. For them there are very few "
        "comparable households with such a member, so the main estimate leans on a small "
        "number of households. The second estimate uses only the households whose estimated "
        f"chance was between 0.01 and 0.99 ({nums.num('derived.share_inside_overlap')}% of "
        "people), where the comparison is better supported. It describes those households, "
        "not all of Nigeria."
    )
    return f"""<section aria-labelledby="result-heading">
<h2 id="result-heading">The main result</h2>
<p class="lead" id="headline">{text.headline(nums)}</p>
<p>{text.comparison_rates(nums)} {text.verdict_rule(nums)}</p>
<div class="p5-pair">
{
        signed_box(
            nums,
            "primary",
            "All households (the pre-registered main estimate)",
            "Standardised to the whole population of Nigeria in households with a member aged "
            "5 or older.",
        )
    }
{
        signed_box(
            nums,
            "overlap_population",
            "Secondary: households where the comparison is better supported",
            "Comparable households without such a member: "
            f"{nums.num('estimates.overlap_population.mu0')}% poor.",
        )
    }
</div>
<p>{overlap}</p>
<p>{text.missing_line(nums)}</p>
<details class="more">
<summary>How the estimated chance of having such a member was spread</summary>
{quantiles}
</details>
<div class="caveat">
<h3 id="reasons-heading">An adjusted association, not a causal effect</h3>
<p>This does not show that disability makes households poorer. Two reasons:</p>
<ol class="sentences">{reasons}</ol>
</div>
<h3 id="measure-heading">How severe difficulty was measured</h3>
<p>{text.misclassification(nums)}</p>
<h3 id="five-heading">The same comparison, five ways</h3>
<p>The main estimate, the better-supported comparison, a familiar survey-weighted linear model
and two secondary definitions (S2: NBS's broad definition; S3: the household head has the
difficulty). They answer slightly different questions, so they are not ranked against each
other: no comparison between them was planned.</p>
{
        figure(
            charts["poverty_headline"],
            "headline-chart",
            "The same figures as a table:",
            dl,
            "five-ways",
            "the main comparison, five ways",
        )
    }
</section>"""


def checks_section(nums: Any, dl: Any) -> str:
    t7_rows = []
    for key, label in (
        ("exposed", "People who are poor, households with a person with a disability (%)"),
        ("unexposed", "People who are poor, households without (%)"),
        ("gap", "Gap (percentage points)"),
    ):
        ok = "yes" if nums.flag(f"table7_{key}_pass") else "no"
        t7_rows.append(
            [
                esc(label),
                nums.value(f"table7_{key}", decimals=1),
                nums.value(f"table7_{key}_nbs", decimals=1),
                ok,
            ]
        )
    t7 = table(
        "Reproducing NBS Table 7 (broad definition, unadjusted)",
        ["Figure", "Ours", "NBS Table 7", "Within tolerance"],
        t7_rows,
        dl=dl,
        table_id="nbs-table-7",
        name="reproducing NBS Table 7",
        provenance=downloads.P5_TABLE7,
        numeric=[False, True, True, False],
    )
    passed = "passed" if nums.flag("table7_all_pass") else "failed"
    rob = table(
        "The main estimate under other reasonable choices, percentage points. Low and High: "
        "the 95% confidence interval",
        ["Choice", "Difference", "Low", "High"],
        [[nums.text(f"estimates.{e}.label"), *est_cells(nums, e)] for e in ROBUSTNESS_ROWS],
        dl=dl,
        table_id="robustness",
        name="the main estimate under other reasonable choices",
        unit="percentage points",
    )
    lozo_ids = [e for e in nums.payload["estimates"] if e.startswith("lozo_")]
    lozo = table(
        "The main estimate with one zone left out at a time (one repetition), percentage "
        "points. Low and High: the 95% confidence interval",
        ["Left out", "Difference", "Low", "High"],
        [[nums.text(f"estimates.{e}.label"), *est_cells(nums, e)] for e in lozo_ids],
        dl=dl,
        table_id="leave-one-zone-out",
        name="the main estimate with one zone left out at a time",
        unit="percentage points",
    )
    sel = "summary.mpi"
    learners = table(
        "How well each method predicted, mean log loss over 5 cross-fitting folds (lower is "
        "better)",
        ["Method", "Poverty model", "Exposure model"],
        [
            [
                esc(label),
                nums.num(f"{sel}.outcome_{key}_mean_loss.value", 1, 4),
                nums.num(f"{sel}.propensity_{key}_mean_loss.value", 1, 4),
            ]
            for key, label in LEARNERS
        ],
        dl=dl,
        table_id="learners",
        name="how well each method predicted (mean log loss)",
    )
    names = dict(LEARNERS)
    chosen_y = names[nums.raw(f"{sel}.outcome_chosen.value_text")].lower()
    chosen_d = names[nums.raw(f"{sel}.propensity_chosen.value_text")].lower()
    as_extreme = nums.raw("derived.placebo_as_extreme")
    placebo_far = (
        "None of them was as far from zero as the real estimate"
        if as_extreme == 0
        else f"{nums.count('derived.placebo_as_extreme')} of them were at least as far from "
        "zero as the real estimate"
    )
    return f"""<section aria-labelledby="checks-heading">
<h2 id="checks-heading">How we checked it</h2>
<p>Every check below was fixed in the pre-registration before any poverty figure was split by
disability. A failure would be reported here, not hidden.</p>
<h3 id="table7-heading">First: reproducing NBS's own figures</h3>
<p>NBS's 2022 report (Table 7) says that, on its broad definition, people in households with a
person with a disability are more often poor. It is a raw comparison, with nothing taken into
account. We rebuilt the poverty index from the survey and checked that it gives the same
figures, within {nums.value("table7_tolerance", decimals=1)} points each. The check
{passed}.</p>
{t7}
<h3 id="benchmark-heading">A familiar benchmark</h3>
<p>A survey-weighted linear model with the same factors, the kind of model most survey
analysts use, gives {nums.est("survey_lpm")} points (95% confidence interval
{nums.ci("survey_lpm")}), against {nums.est("primary")} for the main estimate. It is a check,
not a second answer.</p>
<h3 id="refutations-heading">Checks that should find nothing</h3>
<ul class="sentences">
<li><strong>Fake exposure.</strong> We shuffled which households have a member with a severe
difficulty, within each senatorial district, {nums.value("placebo_n", decimals=0)} times, and
re-ran the analysis each time. The fake estimates averaged
{nums.num("summary.mpi.placebo_mean.value")} points (standard deviation
{nums.num("summary.mpi.placebo_sd.value")}), close to zero as expected, and
{nums.share("placebo_share_ci_excluding_0", decimals=0)} of their intervals left out zero
(about 5% expected). {placebo_far}: empirical p =
{nums.value("placebo_empirical_p", decimals=3)}.</li>
<li><strong>A random extra factor.</strong> {text.rcc_line(nums)}</li>
<li><strong>Leaving out one zone at a time.</strong> The estimate stayed between
{nums.num("derived.leave_one_zone_out.min")} and {nums.num("derived.leave_one_zone_out.max")}
points.</li>
</ul>
<details class="more"><summary>Leave-one-zone-out figures</summary>
{lozo}
</details>
<h3 id="robustness-heading">Other reasonable choices</h3>
<p>Eight other choices fixed in advance (fewer factors, other methods, two other ways of
counting deprivation) give estimates between {nums.num("derived.robustness.min")} and
{nums.num("derived.robustness.max")} points.</p>
{rob}
<h3 id="learners-heading">How the methods were chosen</h3>
<p>The analysis uses double machine learning: one model predicts poverty, another predicts which
households have a member with a severe difficulty, and the two are combined so that errors in
either one matter less. For each model, three methods were scored on households they had not
seen, before any difference was computed. The best one was chosen, unless a simpler one was
within the margin of error. That gave {chosen_y} for poverty and {chosen_d} for the
exposure.</p>
{learners}
</section>"""


def sensitivity_section(nums: Any, dl: Any) -> str:
    bench_rows = []
    for key, label in BENCHMARKS:
        p = f"summary.mpi.bench_{key}"
        bench_rows.append(
            [
                esc(f"As strong as {label}"),
                f"{nums.num(f'{p}_theta_lower.value')} to {nums.num(f'{p}_theta_upper.value')}",
                f"{nums.num(f'{p}_ci_lower.value')} to {nums.num(f'{p}_ci_upper.value')}",
            ]
        )
    bench = table(
        "Where a hidden factor as strong as an observed one would move the main estimate, "
        "percentage points (DoubleML bounds)",
        ["Hidden factor", "Estimate between", "95% interval"],
        bench_rows,
        dl=dl,
        table_id="benchmarks",
        name="hidden factors as strong as measured ones (DoubleML bounds)",
        unit="percentage points",
    )
    sm = table(
        "Weighted linear model (ignoring the survey design), adjusted for hidden factors "
        "benchmarked on the head's education (sensemakr), percentage points. Low and High: "
        "the 95% confidence interval",
        ["Hidden factor", "Difference", "Low", "High"],
        [
            [nums.text(f"estimates.{e}.label"), *est_cells(nums, e)]
            for e in ("sensemakr_1x", "sensemakr_2x", "sensemakr_3x")
        ],
        dl=dl,
        table_id="sensemakr",
        name="the linear model adjusted for hidden factors (sensemakr)",
        unit="percentage points",
    )
    return f"""<section aria-labelledby="sensitivity-heading">
<h2 id="sensitivity-heading">How strong would a hidden factor need to be?</h2>
<p>Nothing that was not measured can be ruled out. What can be said is how strong such a factor
would need to be to change the answer. No decision depended on these numbers; they are reported
as they came out.</p>
<h3 id="rv-heading">The worst case</h3>
<p>Suppose a hidden factor pushed in exactly the direction that matters. If it accounted for
{nums.share("rv")} of what is left unexplained in both poverty and in which households have
such a member, it could bring the main estimate to zero. At {nums.share("rva")}, the 95%
interval would include zero. These robustness values are small: the comparison is fragile to a
factor of this kind. A factor of {nums.share("default_cf_y", decimals=0)} strength would leave
the estimate anywhere between {nums.num("summary.mpi.default_theta_lower.value")} and
{nums.num("summary.mpi.default_theta_upper.value")} points.</p>
<h3 id="bench-heading">Compared with factors we did measure</h3>
<p>Measured factors give a sense of scale. A hidden factor as strong as each of these, and lined
up with poverty and exposure the way each of them is, would move the estimate only a little:</p>
{bench}
<p>The worst case and these comparisons answer different questions: the worst case assumes the
hidden factor lines up perfectly, while the measured factors line up only weakly.</p>
<h3 id="sensemakr-heading">A second method</h3>
<p>The same question asked of a weighted linear model (sensemakr; this model ignores the survey
design, so its standard error is too small) gives
{nums.num("summary.mpi.sensemakr_estimate.value")} points before adjustment, a robustness value
of {nums.share("sensemakr_rv_q")}, and these adjusted figures:</p>
{sm}
<h3 id="evalue-heading">The E-value</h3>
<p>People in households with such a member are {nums.value("evalue_rr")} times as likely to be
poor (95% confidence interval {nums.value("evalue_rr_ci_low")} to
{nums.value("evalue_rr_ci_high")}). The E-value is {nums.value("evalue")}: a hidden factor
would need to make both poverty and having such a member about {nums.value("evalue")} times as
likely to explain the whole difference away, and {nums.value("evalue_ci")} times to bring the
interval to 1. Two cautions:</p>
<ul class="sentences">
<li>The E-value for the interval ignores the uncertainty in the comparison households' poverty
rate.</li>
<li>With {nums.num("estimates.primary.mu0")}% of comparison households poor, the risk ratio
cannot go above about {nums.num("derived.rr_ceiling", 1, 2)} (1 divided by
{nums.num("estimates.primary.mu0", 1, 3)}), so E-values here are small by construction.</li>
</ul>
</section>"""


def secondaries_section(nums: Any, charts: Mapping[str, Mapping[str, Any]], dl: Any) -> str:
    rows = []
    for eid in SECONDARY_ROWS:
        cells = est_cells(nums, eid)
        if eid in HOLM:
            supported = nums.raw(f"estimates.{eid}.supported")
            holm = nums.p(f"estimates.{eid}.holm_p")
            status = "supported" if supported else "not supported"
        else:
            holm, status = "", "descriptive"
        label = nums.text(f"estimates.{eid}.label")
        if eid.startswith("s4_"):
            label = f"S4: {label} (points out of 100)"
        rows.append([label, *cells, holm, status])
    sec = table(
        "Secondary questions. S1 and S4 in points out of 100, the others in percentage points. "
        "Low and High: the 95% confidence interval; Holm: the p-value corrected across S1-S3",
        ["Question", "Difference", "Low", "High", "Holm", "Wording"],
        rows,
        dl=dl,
        table_id="secondary-questions",
        name="secondary questions S1 to S6",
        numeric=[False, True, True, True, True, False],
    )
    x1_ids = [e for e in nums.payload["estimates"] if e.startswith("x1_")]
    x1 = table(
        "The main comparison within groups (exploratory X1), percentage points. Low and High: "
        "the 95% confidence interval",
        ["Group", "Difference", "Low", "High", "Households", "With such a member"],
        [
            [
                nums.text(f"estimates.{e}.label"),
                *est_cells(nums, e),
                nums.count(f"estimates.{e}.n"),
                (
                    nums.count(f"estimates.{e}.n_exposed")
                    if not nums.raw(f"estimates.{e}.suppressed")
                    else "under 30"
                ),
            ]
            for e in x1_ids
        ],
        dl=dl,
        table_id="within-groups",
        name="the main comparison within groups (exploratory X1)",
        unit="percentage points",
    )
    supported = [e for e in HOLM if nums.raw(f"estimates.{e}.supported")]
    holm_line = (
        "All three of S1, S2 and S3 are supported after correcting for testing three questions "
        "(Holm's method)."
        if len(supported) == 3
        else f"{len(supported)} of S1, S2 and S3 are supported after correcting for testing "
        "three questions (Holm's method)."
    )
    return f"""<section aria-labelledby="secondaries-heading">
<h2 id="secondaries-heading">Other questions we registered</h2>
<p>Each is labelled secondary. S1 (the deprivation score instead of the poor or not-poor cut),
S2 (NBS's broad definition) and S3 (the head has the difficulty) were registered as a family:
{holm_line} S4 to S6 are descriptive.</p>
{sec}
<h3 id="dimensions-heading">Where the difference sits (S4)</h3>
<p>The poverty index has four dimensions. This shows how much of the difference in the
deprivation score (S1) sits in each. It is descriptive: it shows where, not why. The four parts
are separate estimates and do not add exactly to S1.</p>
{
        figure(
            charts["poverty_dimensions"],
            "dimensions-chart",
            "The same figures as a table:",
            dl,
            "dimensions",
            "the difference by MPI dimension (S4)",
        )
    }
<details class="more">
<summary>Within urban and rural areas and within each zone (exploratory)</summary>
<p>Exploratory and noisy: each group has few households with such a member, so these
intervals are wide. They are descriptions, not findings, and are not compared with each
other.</p>
{x1}
</details>
</section>"""


def ghs_section(nums: Any, dl: Any) -> str:
    def work_plain() -> str:
        lo, hi = nums.raw("estimates.ghs_dwork.ci_low"), nums.raw("estimates.ghs_dwork.ci_high")
        if hi < 0:
            return (
                "In plain words: the share who worked went down by more, or up by less, among "
                "people whose severe difficulty began between the rounds than among comparable "
                "people without onset."
            )
        if lo > 0:
            return (
                "In plain words: the share who worked went up by more, or down by less, among "
                "people whose severe difficulty began between the rounds."
            )
        return "The interval includes zero: the survey cannot show a difference."

    def consumption_plain() -> str:
        lo = nums.raw("estimates.ghs_dlog_consumption.ci_low")
        hi = nums.raw("estimates.ghs_dlog_consumption.ci_high")
        if lo <= 0 <= hi:
            return (
                "The interval includes zero: the survey cannot show a difference in how "
                "household consumption changed."
            )
        return "The interval does not include zero."

    OUTCOME_WORDS = {"dlog_consumption": "consumption", "dwork": "work"}

    def mde(outcome: str) -> str:
        run = "analysed" if nums.flag(f"{outcome}_run", "ghs") else "not analysed"
        value = nums.value(f"{outcome}_mde_sd", "ghs", 2)
        return (
            f"For {OUTCOME_WORDS[outcome]}, the smallest detectable difference was {value} "
            f"standard deviations, so it was {run}."
        )

    agree = max(
        nums.raw("summary.ghs.dlog_consumption_r_max_abs_diff.value"),
        nums.raw("summary.ghs.dwork_r_max_abs_diff.value"),
    )
    r_line = (
        "R (fixest) gave the same estimates and intervals to at least six decimal places."
        if agree < 5e-7
        else "R (fixest) gave slightly different numbers; both are in the published file."
    )
    stay = nums.raw("summary.ghs.attrition_age_stayers.value")
    leave = nums.raw("summary.ghs.attrition_age_attriters.value")
    younger = (
        "People not found again were younger on average."
        if leave < stay
        else "People not found again were not younger on average."
    )
    attr_rows = []
    for key, label in (
        ("age", "Age (years)"),
        ("female", "Women (share)"),
        ("urban", "Urban (share)"),
        ("severe_w4", "Severe difficulty in 2018/19 (share)"),
    ):
        p = f"summary.ghs.attrition_{key}"
        attr_rows.append(
            [
                esc(label),
                nums.num(f"{p}_stayers.value", 1, 2),
                nums.num(f"{p}_attriters.value", 1, 2),
                nums.num(f"{p}_standardised_difference.value", 1, 2),
            ]
        )
    attrition = table(
        "People found again in 2023/24 (stayers) and not found (leavers), on 2018/19 "
        "characteristics",
        ["Characteristic", "Stayers", "Leavers", "Standardised difference"],
        attr_rows,
        dl=dl,
        table_id="attrition",
        name="who was found again in 2023/24 (attrition)",
        provenance=downloads.P5_GHS,
    )
    ghs = table(
        "Exploratory: change between 2018/19 and 2023/24 for people whose severe difficulty "
        "began between the rounds, against comparable people. Low and High: the 95% "
        "confidence interval",
        ["Outcome", "Difference", "Low", "High", "People", "With onset"],
        [
            [
                esc("Log household consumption per person (log points)"),
                *est_cells(nums, "ghs_dlog_consumption", 3),
                nums.count("estimates.ghs_dlog_consumption.n"),
                nums.count("estimates.ghs_dlog_consumption.n_exposed"),
            ],
            [
                esc("Worked in the last 7 days (percentage points)"),
                *est_cells(nums, "ghs_dwork"),
                nums.count("estimates.ghs_dwork.n"),
                nums.count("estimates.ghs_dwork.n_exposed"),
            ],
        ],
        dl=dl,
        table_id="ghs-change",
        name="change for people whose severe difficulty began (exploratory)",
        provenance=downloads.P5_GHS,
    )
    return f"""<section aria-labelledby="ghs-heading">
<h2 id="ghs-heading">Exploratory: the same people five years apart</h2>
<div class="caveat">
<h3 id="ghs-label-heading">Exploratory, not confirmatory</h3>
<p>This part compares only two survey rounds, five years apart. It was registered as
exploratory: two outcomes, intervals only, no claim that a difference is supported.</p>
</div>
<p>The General Household Survey-Panel visited the same households in 2018/19 and 2023/24, and
both rounds asked the Washington Group's six questions. {text.ghs_sample_line(nums)}</p>
<p>A rule fixed in advance said each outcome is analysed only if the survey could detect a
difference of at most half a standard deviation of the change.
{mde("dlog_consumption")} {mde("dwork")}</p>
{ghs}
<ul class="sentences">
<li><strong>Consumption:</strong> {nums.est("ghs_dlog_consumption", decimals=3)} log points
(95% confidence interval {nums.ci("ghs_dlog_consumption", 3)}). {consumption_plain()}</li>
<li><strong>Work:</strong> {nums.est("ghs_dwork")} percentage points (95% confidence interval
{nums.ci("ghs_dwork")}). {work_plain()}</li>
</ul>
<p>{r_line} Both models take into account age band, sex, zone and urban or rural, and use the
survey's weight for people followed over time.</p>
<p><strong>What cannot be tested.</strong> The comparison assumes that, without the onset, people
with onset would have changed like the comparison group. That assumption cannot be checked
with two rounds. Onset is only seen at the second round, so the order of change (the
difficulty first, or the change in work first) is unknown.</p>
<p><strong>Questions that differ between the rounds.</strong> In 2023/24 the communication
question adds "using your usual language". The work questions cover the same three kinds of
work in both rounds (for someone outside the household, on the household's farm, and in the
person's own business), but the wording differs: in 2018/19 the business question says "on
their own account or in a business", in 2023/24 "a non-farm household business". The
2023/24 questions on helping in another member's business or farm are not used, because
2018/19 has no separate helping question; the 2018/19 farm question probably includes
helpers, which may make work in 2023/24 look slightly lower.</p>
<details class="more"><summary>Who was found again (attrition)</summary>
<p>{younger} No outcome is involved in this comparison.</p>
{attrition}
</details>
</section>"""


def reading_section(nums: Any) -> str:
    return f"""<section aria-labelledby="reading-heading">
<h2 id="reading-heading">How to read survey figures</h2>
<p>Four short examples, using this page's own numbers.</p>
<h3 id="read-interval-heading">What a 95% confidence interval means</h3>
<p>The main estimate is {nums.est("primary")} points, with a 95% confidence interval of
{nums.ci("primary")}. A survey talks to a sample of households, not to everyone, so a
different sample would give a slightly different figure. The interval shows that uncertainty: if
the survey were repeated many times and an interval made the same way each time, about 95 in
100 of them would contain the true value. This interval does not include zero, so the survey
can show a difference. It does not cover other kinds of uncertainty, such as factors that were
not measured.</p>
<h3 id="read-weights-heading">Survey weights</h3>
<p>Each household in the survey stands for many people in Nigeria, and some kinds of household
were sampled more than others. The weights used here are population weights (the household's
weight times its number of members), so that the {nums.n("weights_n")} households in the
analysis represent the whole population. The price is precision: with these unequal weights,
the households carry about as much information as
{nums.count("summary.mpi.kish_effective_n.value")} households with equal weights would.</p>
<h3 id="read-association-heading">An adjusted association, not an effect</h3>
<p>On rainy days, more people carry umbrellas and more pavements are wet. Umbrellas do not wet
pavements: the rain does both. Comparing only days with the same weather takes the rain out of
the comparison. That is what adjusting does. Here we compared households in the same senatorial
district, urban or rural, with the same mix of ages, and with a head of the same sex and similar
age and education. What remains is an adjusted association. It could still come from a factor
nobody measured, or from poverty coming first, so it is not proof that one leads to the
other.</p>
<h3 id="read-points-heading">Percentage points and percent</h3>
<p>Among comparable households without such a member, {nums.num("estimates.primary.mu0")}% of
people are poor; standardised to the same mix of households, the figure with such a member would
be {nums.num("derived.primary_implied")}%. The difference is
{nums.est("primary")} percentage points: points are a simple subtraction of two percentages.
Said another way, the share is {nums.num("derived.relative_increase", 100, 0)}% higher than
the comparison households' share: percent compares the difference with the starting figure.
Both are correct; points are used on this page because they do not depend on the starting
figure.</p>
</section>"""


def registration_section(nums: Any) -> str:
    reg = "summary.mpi"
    osf = nums.raw(f"{reg}.osf_url.value_text")
    commit = nums.raw(f"{reg}.freeze_commit.value_text")
    osf_label = esc("OSF registration " + osf.rstrip("/").rsplit("/", 1)[-1])
    commit_label = esc(f"frozen commit {commit[:7]} on GitHub")
    return f"""<section aria-labelledby="registration-heading">
<h2 id="registration-heading">Registration, data and citations</h2>
<div class="p5-registration">
<h3 id="osf-heading">Registered before the analysis</h3>
<dl class="facts">
<dt>Registration</dt><dd><a href="{esc(osf)}"
aria-label="{osf_label}">{nums.text(f"{reg}.osf_url.value_text")}</a>
(Open Science Framework, {text.OSF_TEMPLATE} template)</dd>
<dt>Registered</dt><dd>{nums.text(f"{reg}.registered_utc.value_text")}</dd>
<dt>Plan and code frozen</dt><dd>tag {nums.text(f"{reg}.freeze_tag.value_text")}, commit
<a href="{REPO}/commit/{esc(commit)}" aria-label="{commit_label}">
<code>{nums.text(f"{reg}.freeze_commit.value_text")}</code>
</a></dd>
<dt>Deviations from the plan</dt><dd>{nums.text(f"{reg}.deviations.value_text")} so far
(<a href="{REPO}/blob/main/docs/preregistration-deviations.md">deviations log</a>)</dd>
</dl>
<p><a href="{text.PREREG_AT_FREEZE}">The pre-registration as frozen</a> (on GitHub, at the
freeze tag). The published estimates and checks are
<a href="{REPO}/tree/main/data/public/aggregates">on GitHub</a>
(<code>p5_mpi_estimates.csv</code>, <code>p5_mpi_summary.csv</code>,
<code>p5_ghs_estimates.csv</code>, <code>p5_ghs_summary.csv</code>).</p>
</div>
<h3 id="brief-heading">The policy brief</h3>
<p><a href="./{BRIEF_PDF}" download>Download the two-page policy brief (PDF)</a>, or read
<a href="{REPO}/blob/main/{BRIEF_MD}">the same brief as text on GitHub</a>.</p>
<h3 id="sources-heading">Data sources and citations</h3>
<ul class="sentences">
<li>National Bureau of Statistics (NBS), <cite>Multidimensional Poverty Index Survey 2021</cite>,
version 1.0 (NGA-NBS-MPI-2021-v1.0). Estimates by Curb Cut; aggregated reporting only, and an
electronic copy of this publication goes to the National Data Archive.</li>
<li>NBS, <cite>Nigeria Multidimensional Poverty Index (2022)</cite>, Table 7, for the published
comparison reproduced above.</li>
<li>NBS and the World Bank, <cite>General Household Survey-Panel</cite>, Wave 4 (2018/19,
NGA_2018_GHSP-W4_v03_M) and Wave 5 (2023/24, NGA_2023_GHSP-W5_v02_M), World Bank Microdata
Library.</li>
<li>Only estimates that passed the project's disclosure check leave the restricted zone: no
estimate rests on fewer than 30 households (or people) in either group, and the smallest group
behind any published estimate has {nums.count("derived.smallest_group")} (households for MPI,
people for GHS). No household-level
data are published.</li>
</ul>
</section>"""


def head_html(plain: Any) -> str:
    title = "Disability and poverty: Curb Cut"
    description = (
        "Adjusted association, pre-registered, NBS MPI 2021: people in households with a "
        f"severely disabled member are {plain.est('primary')} percentage points (95% confidence "
        f"interval {plain.ci('primary')}) more likely to be multidimensionally poor than people "
        "in comparable households. With checks and plain-English explanations."
    )
    return (
        '<!doctype html>\n<html lang="en-NG">\n<head>\n<meta charset="utf-8" />\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1" />\n'
        '<meta name="color-scheme" content="light dark" />\n'
        f"<title>{esc(title)}</title>\n"
        f'<meta name="description" content="{esc(description)}" />\n'
        f'<link rel="icon" type="image/svg+xml" href="{pages.FAVICON}" />\n'
        '<link rel="stylesheet" href="./src/style.css" />\n'
    )


def nav_html() -> str:
    return (
        '<nav class="site-nav" aria-label="Site"><ul>'
        '<li><a href="./">Main page</a></li>'
        '<li><a href="./states/">State pages</a></li>'
        '<li><a href="./poverty.html" aria-current="page">Disability and poverty</a></li>'
        '<li><a href="./methodology.html">Methodology</a></li>'
        '<li><a href="./data-dictionary.html">Data dictionary</a></li>'
        "</ul></nav>"
    )


def page_downloads(payload: Mapping[str, Any], site_url: str) -> Any:
    """An empty collector for the page's table downloads."""
    if not site_url.endswith("/"):
        site_url += "/"
    collector = PageDownloads(f"{site_url}poverty.html", "poverty", DOWNLOADS_HREF)
    collector.nums = text.Numbers(payload, html_mode=False)
    return collector


def page_html(
    payload: Mapping[str, Any], charts: Mapping[str, Mapping[str, Any]], dl: Any = None
) -> str:
    """The page. Its tables' download files go into ``dl`` (``page_downloads``)."""
    nums = text.Numbers(payload, html_mode=True)
    if dl is None:
        dl = page_downloads(payload, pages.DEFAULT_SITE_URL)
    css = dot_svg.theme_css(charts["poverty_headline"])
    plain = text.Numbers(payload, html_mode=False)
    if plain.raw("derived.verdict") != "higher":
        raise ValueError("the page's description is written for the 'higher' verdict")
    return f"""{head_html(plain)}<style>{css}</style>
</head>
<body>
<a class="skip-link" href="#main">Skip to main content</a>
<div class="flag-band" aria-hidden="true"></div>
<header class="site-header"><p class="site-name"><a href="./">Curb Cut</a></p>
{nav_html()}</header>
<main id="main" tabindex="-1" class="poverty-page">
<h1>Disability and poverty in Nigeria</h1>
<p>Are people in households with a severely disabled member more often poor? This page answers
with the National Bureau of Statistics' Multidimensional Poverty Index survey 2021, in an
analysis whose plan was registered publicly before any poverty figure was split by disability.
Poverty here is NBS's multidimensional poverty: being deprived in at least 26% of a weighted
list of health, education, living standards, and work and shocks.</p>
{result_section(nums, charts, dl)}
{checks_section(nums, dl)}
{sensitivity_section(nums, dl)}
{secondaries_section(nums, charts, dl)}
{ghs_section(nums, dl)}
{reading_section(nums)}
{registration_section(nums)}
</main>
<footer class="site-footer">
<h2 class="footer-heading">Accessibility and feedback</h2>
{REPORT_HTML}
<p><a href="./methodology.html">Methodology: definitions, sources and limits</a>.
<a href="./">Back to the main page</a>. Source code and data notes:
<a href="{REPO}">github.com/batestguy/curb-cut</a>.</p>
</footer>
</body>
</html>
"""


def build(data_dir: Path, page: Path, site_url: str = pages.DEFAULT_SITE_URL) -> str:
    """Write the page, and its tables' downloads to ``data_dir/downloads/poverty/``."""
    payload = json.loads((data_dir / "poverty.json").read_text(encoding="utf-8"))
    charts = {
        name: json.loads((data_dir / "charts" / f"{name}.json").read_text(encoding="utf-8"))
        for name in ("poverty_headline", "poverty_dimensions")
    }
    dl = page_downloads(payload, site_url)
    out = page_html(payload, charts, dl)
    bad = text.forbidden(out)
    if bad:
        raise ValueError(f"wording the pre-registration rules out: {sorted(set(bad))}")
    dl.check_linked(out)
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text(out, encoding="utf-8", newline="\n")
    dl.write(data_dir / "downloads")
    return out


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build site/poverty.html (P5 results).")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--page", type=Path, default=DEFAULT_PAGE)
    parser.add_argument("--site-url", default=os.environ.get("SITE_URL", pages.DEFAULT_SITE_URL))
    args = parser.parse_args(argv)
    try:
        out = build(args.data_dir, args.page, args.site_url)
    except (ValueError, KeyError) as error:
        print(f"Poverty page failed: {error!r}", file=sys.stderr)
        return 1
    print(f"wrote {args.page} ({len(out.encode('utf-8')):,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
