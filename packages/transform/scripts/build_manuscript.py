# ruff: noqa: RUF001, E501 - the file is mostly manuscript prose: typographic dashes and
# signs are intended, and table rows and the title cannot be wrapped.
"""Write the P5 journal manuscript (``docs/paper/p5-manuscript.md``) from the exported data.

Run after ``export_marts.py``, from the repo root:
``uv run python packages/transform/scripts/build_manuscript.py [--docx] [--check]``.

The target is *Disability, CBR and Inclusive Development* (DCIDJ): original research
article, at most 4,000 words excluding the abstract, tables and references; structured
abstract of at most 300 words; up to six keywords not in the title; APA references; UK
English; blind review (author guidelines read 2026-11-10 at
https://dcidj.uog.edu.et/index.php/up-j-dcbrid/about/submissions).

As for the brief (``build_brief.py``), every number comes from
``site/public/data/poverty.json`` through ``poverty_text.Numbers``; the only exceptions are
the exposure shares of the pre-registered exposure check, which are quoted from the frozen
pre-registration (``PREREG_EXPOSURE``; a test checks that file still says so). The text is
refused if it uses wording the pre-registration rules out (``poverty_text.forbidden``), if
the counted words exceed the limit, or if the abstract is too long.

* ``--check``: rebuild in memory and fail if the committed markdown differs;
* ``--docx``: also run pandoc (``--pandoc`` or ``$PANDOC``) to write two Word files to the
  git-ignored ``docs/paper/out/``: the full manuscript and a blinded copy for review, in
  which every link and name that identifies the author is withheld (:func:`blind`).
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import os
import re
import subprocess
import sys
import zipfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from types import ModuleType
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DATA = ROOT / "site" / "public" / "data" / "poverty.json"
DEFAULT_TABLE1 = ROOT / "data" / "public" / "aggregates" / "p5_table1.csv"
"""Table 1 (household characteristics by exposure), written by the disclosure gate
(``curbcut_ingest.restricted.p5_table1``); committed, so CI can rebuild the manuscript."""
PAPER_DIR = ROOT / "docs" / "paper"
DEFAULT_MD = PAPER_DIR / "p5-manuscript.md"
OUT_DIR = PAPER_DIR / "out"
DEFAULT_PANDOC = "C:/Users/TOSHIBA/miniconda3/Library/bin/pandoc"

WORD_LIMIT = 4000
ABSTRACT_LIMIT = 300
PAGE_URL = "https://batestguy.github.io/curb-cut/poverty.html"
REPO_URL = "https://github.com/batestguy/curb-cut"
CODE_DOI = "https://doi.org/10.5281/zenodo.24050358"

# Quoted from the frozen pre-registration, section 2.2 item 9 (exposure only, before
# registration). tests_py/test_build_manuscript.py checks the file still contains them.
PREREG_EXPOSURE = {"primary": "1.33%", "s2": "11.07%", "s5": "8.78%", "s6": "0.92%"}

# Markers that delimit what the word limit counts (main text only).
BODY_START = "<!-- body -->"
BODY_END = "<!-- end body -->"


def _load(name: str) -> ModuleType:
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(f"{name}.py"))
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


text = _load("poverty_text")


def pval(nums: Any, path: str) -> str:
    """APA style: exact p to three decimals, no leading zero; below .001 as p < .001."""
    value = nums.raw(path)
    if value is None:
        raise ValueError(f"{path} is missing")
    value = float(value)
    return "p < .001" if value < 0.001 else f"p = {value:.3f}".replace("0.", ".", 1)


def row(nums: Any, eid: str, label: str | None = None, *, p: bool = True) -> str:
    """One table row: label, exposed households, estimate, 95% CI (and p)."""
    e = f"estimates.{eid}"
    name = label or str(nums.raw(f"{e}.label"))
    if nums.raw(f"{e}.suppressed"):
        # The disclosure gate withheld it (a group under 30): say so, never show it.
        return "| " + " | ".join([name, "<30", "suppressed", "–"] + (["–"] if p else [])) + " |"
    cells = [name, nums.count(f"{e}.n_exposed"), nums.est(eid), nums.ci(eid)]
    if p:
        cells.append(pval(nums, f"{e}.pval") if nums.raw(f"{e}.pval") is not None else "–")
    return "| " + " | ".join(cells) + " |"


def guards(nums: Any) -> None:
    """Each comparison the prose states in words, checked against the data, so that a change
    in the published estimates cannot leave the text saying something the numbers do not."""

    def e(eid: str, field: str = "estimate") -> float:
        return float(nums.raw(f"estimates.{eid}.{field}"))

    def s(item: str, analysis: str = "mpi") -> Any:
        return nums.raw(f"summary.{analysis}.{item}.value")

    checks = {
        "verdict higher": nums.raw("derived.verdict") == "higher",
        "primary interval above +2 points": e("primary", "ci_low") > 0.02,
        "S1-S3 supported after Holm": all(
            nums.raw(f"estimates.{k}.supported") for k in ("s1_score", "s2_broad", "s3_head")
        ),
        "no deviations": nums.raw("summary.mpi.deviations.value_text") == "none",
        "S5 below primary": e("s5_unasked_severe") < e("primary"),
        "S6 interval contains primary": e("s6_routing_free", "ci_low")
        <= e("primary")
        <= e("s6_routing_free", "ci_high"),
        "primary above S2": e("primary") > e("s2_broad"),
        "S2 interval contains the unadjusted gap": e("s2_broad", "ci_high") * 100
        >= float(s("table7_gap")),
        "overlap below primary": e("overlap_population") < e("primary"),
        "overlap interval above zero": e("overlap_population", "ci_low") > 0,
        "LPM below primary": e("survey_lpm") < e("primary"),
        "urban above rural": e("x1_sector_urban") > e("x1_sector_rural"),
        "S4 health and work above zero": e("s4_health", "ci_low") > 0
        and e("s4_work_and_shocks", "ci_low") > 0,
        "S4 education and living standards include zero": e("s4_education", "ci_low")
        <= 0
        <= e("s4_education", "ci_high")
        and e("s4_living_standards", "ci_low") <= 0 <= e("s4_living_standards", "ci_high"),
        "no placebo as extreme": nums.raw("derived.placebo_as_extreme") == 0,
        "random covariate within allowance": bool(s("rcc_pass")),
        "Table 7 check passed": bool(s("table7_all_pass")),
        "sensemakr 3x interval includes zero": e("sensemakr_3x", "ci_low")
        <= 0
        <= e("sensemakr_3x", "ci_high"),
        "benchmarks above zero": float(nums.raw("derived.benchmarks.min")) > 0,
        "GHS work interval below zero": e("ghs_dwork", "ci_high") < 0,
        "GHS consumption interval includes zero": e("ghs_dlog_consumption", "ci_low")
        <= 0
        <= e("ghs_dlog_consumption", "ci_high"),
        "GHS attriters younger and more often severe": s("attrition_age_attriters", "ghs")
        < s("attrition_age_stayers", "ghs")
        and s("attrition_severe_w4_attriters", "ghs") > s("attrition_severe_w4_stayers", "ghs"),
        "propensity learner not the lowest-loss one": nums.raw(
            "summary.mpi.propensity_chosen.value_text"
        )
        != nums.raw("summary.mpi.propensity_lowest.value_text"),
        "missing counts published": not nums.raw("summary.mpi.missing_poor_households.suppressed")
        and not nums.raw("summary.mpi.missing_exposure_primary_households.suppressed"),
    }
    failed = [name for name, ok in checks.items() if not ok]
    if failed:
        raise ValueError(
            f"the text is written for the 1 November 2026 results; now false: {failed}"
        )


T1_LABELS = {
    "zone": "Zone",
    "sector": "Sector",
    "head_sex": "Head's sex",
    "head_age": "Head's age (years)",
    "head_education": "Head's highest education",
    "age_structure": "Household members (mean number)",
}
T1_CATEGORIES = {
    "none": "None",
    "non_formal": "Non-formal",
    "preschool": "Pre-school",
    "primary_incomplete": "Primary, not completed",
    "primary": "Primary completed",
    "secondary": "Secondary",
    "higher": "Higher",
    "missing": "Missing",
}
T1_ORDER = {
    "head_age": ["under 30", "30-44", "45-59", "60+", "missing"],
    "head_education": list(T1_CATEGORIES),
    "age_structure": [
        "household members, all ages",
        "members aged 0-4",
        "members aged 5",
        "members aged 6-14",
        "members aged 15-17",
        "members aged 18-59",
        "members aged 60-69",
        "members aged 70+",
    ],
}


def load_table1(path: Path = DEFAULT_TABLE1) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    if not rows or any(r["table"] != "table1" for r in rows):
        raise ValueError(f"{path} is not the Table 1 file")
    return rows


class Table1:
    """Cells of Table 1 by (characteristic, category, group)."""

    def __init__(self, rows: list[dict[str, str]]) -> None:
        self.rows = rows
        self.cells = {(r["characteristic"], r["category"], r["group"]): r for r in rows}

    def cell(self, char: str, cat: str, group: str) -> dict[str, str]:
        return self.cells[(char, cat, group)]

    def value(self, char: str, cat: str, group: str) -> float:
        cell = self.cell(char, cat, group)
        if cell["suppressed"] == "True" or cell["value"] == "":
            raise ValueError(f"Table 1 cell {char}/{cat}/{group} is suppressed")
        return float(cell["value"])

    def shown(self, char: str, cat: str, group: str) -> str:
        cell = self.cell(char, cat, group)
        if cell["suppressed"] == "True":
            return "suppressed"
        value = float(cell["value"])
        if cell["kind"] == "mean":
            return text.fixed(value, 1)
        return f"{text.fixed(100 * value, 1)} ({int(float(cell['n'])):,})"

    def categories(self, char: str) -> list[str]:
        found = {r["category"] for r in self.rows if r["characteristic"] == char}
        order = T1_ORDER.get(char, sorted(found))
        return [c for c in order if c in found] + sorted(found - set(order))


def table1_md(t: Table1) -> str:
    lines = [
        "**Table 1.** Household characteristics by exposure, primary analysis sample, Nigeria "
        "MPI Survey 2021: weighted % of people (unweighted households), or weighted mean.",
        "",
        "| Characteristic | Exposed | Unexposed |",
        "|---|---|---|",
        f"| Households (n) | {int(float(t.cell('households', 'all', 'exposed')['n'])):,} | "
        f"{int(float(t.cell('households', 'all', 'unexposed')['n'])):,} |",
    ]
    for char, label in T1_LABELS.items():
        lines.append(f"| **{label}** | | |")
        for cat in t.categories(char):
            name = T1_CATEGORIES.get(cat, cat) if char == "head_education" else cat
            name = name[0].upper() + name[1:]
            lines.append(
                f"| {name} | {t.shown(char, cat, 'exposed')} | {t.shown(char, cat, 'unexposed')} |"
            )
    lines += [
        "",
        "*Note:* Not pre-registered; descriptive. Weighted by the population weight. Cells from "
        "fewer than 30 households are suppressed, with a second cell suppressed where one "
        "could otherwise be worked out from the rest.",
    ]
    return "\n".join(lines)


def table1_guards(t: Table1) -> None:
    def gt(char: str, cat: str) -> bool:
        return t.value(char, cat, "exposed") > t.value(char, cat, "unexposed")

    checks = {
        "exposed households larger": gt("age_structure", "household members, all ages"),
        "more members 70+": gt("age_structure", "members aged 70+"),
        "head 60+ more often": gt("head_age", "60+"),
        "female head more often": gt("head_sex", "female"),
        "head without education more often": gt("head_education", "none"),
        "more often North West and South South": gt("zone", "North West")
        and gt("zone", "South South"),
    }
    failed = [name for name, ok in checks.items() if not ok]
    if failed:
        raise ValueError(f"the Table 1 sentence no longer holds: {failed}")


def manuscript_md(payload: Mapping[str, Any], table1_rows: list[dict[str, str]]) -> str:
    nums = text.Numbers(payload, html_mode=False)
    if nums.raw("derived.verdict") != "higher":
        raise ValueError("the manuscript is written for the 'higher' verdict; rewrite it first")
    guards(nums)
    table = Table1(table1_rows)
    table1_guards(table)

    def t1(char: str, cat: str, group: str = "exposed") -> str:
        return text.fixed(100 * table.value(char, cat, group), 1) + "%"

    def t1m(cat: str, group: str = "exposed") -> str:
        return text.fixed(table.value("age_structure", cat, group), 1)

    m = "summary.mpi"

    def sv(item: str, analysis: str = "mpi") -> str:
        return f"summary.{analysis}.{item}.value"

    def pts(item: str, decimals: int = 1) -> str:
        """A summary proportion shown in percentage points."""
        return nums.num(sv(item), 100, decimals)

    def apa_p(item: str) -> str:
        return nums.value(item, decimals=3).replace("0.", ".", 1)

    ghs_line = text.ghs_sample_line(nums)
    ghs_line = ghs_line[0].lower() + ghs_line[1:]
    osf = nums.text(f"{m}.osf_url.value_text")
    reg_utc = nums.text(f"{m}.registered_utc.value_text")
    deviations = nums.text(f"{m}.deviations.value_text")
    ex = PREREG_EXPOSURE
    n_sample = round(float(nums.raw(sv("households_in_sample"))))
    n_analysed = round(float(nums.raw(sv("weights_n"))))
    n_poor = round(float(nums.raw(sv("missing_poor_households"))))
    n_exp = round(float(nums.raw(sv("missing_exposure_primary_households"))))
    n_excluded = n_sample - n_analysed
    n_both = n_poor + n_exp - n_excluded
    both = f"; {n_both:,} had both" if n_both > 0 else ""
    learner = {
        "logistic": "penalised logistic regression",
        "forest": "random forest",
        "boosting": "gradient boosting",
    }

    abstract = f"""**Aim:** To estimate how much more often people in Nigerian households that include
a member with a severe functional difficulty are multidimensionally poor than people in
comparable households without one.

**Methods:** Pre-registered secondary analysis of the National Bureau of Statistics
Multidimensional Poverty Index (MPI) Survey 2021 ({nums.n("weights_n")} households). Exposure
was a household member aged 5 or older with a lot of difficulty, or unable, in at least one
functional domain. The outcome was multidimensional poverty (deprivation score of 26% or
more), rebuilt from the survey files. A population-weighted standardised difference was
estimated with double machine learning, adjusting for place, household age structure and the
household head's sex, age and education.

**Results:** People in exposed households ({nums.count("estimates.primary.n_exposed")}
households) were {nums.est("primary")} percentage points more likely to be multidimensionally
poor (95% CI {nums.ci("primary")}; {pval(nums, "estimates.primary.pval")}) than people in
comparable households, where {nums.num("estimates.primary.mu0")}% were poor. Among households
with better comparison support the difference was {nums.est("overlap_population")} points
({nums.ci("overlap_population")}). The gap lay mostly in health and in work and shocks.
Other learners and adjustment sets gave {nums.num("derived.robustness.min")} to
{nums.num("derived.robustness.max")} points; a survey-weighted linear model gave
{nums.est("survey_lpm")}.

**Conclusions:** Multidimensional poverty is more common in households that include a person
with a severe functional difficulty (an adjusted association). Recording disability in
poverty programmes and social registers could help reach these households.

**Limitations:** This is an adjusted association, not a causal effect: earlier poverty can
lead to disability, and a hidden factor much weaker than those measured could explain the
difference if aligned with both. The survey asked severity of seeing, hearing and walking
only of aid users."""

    keywords = (
        "functional difficulty; Alkire–Foster; double machine learning; pre-registration; "
        "social protection; sub-Saharan Africa"
    )

    body = f"""## Introduction

The relationship between disability and poverty is widely recognised but remains
ill-defined and under-researched (Groce et al., 2011). However poverty is defined, it is
closely related to disability (Palmer, 2011), and the relationship is often described as a
"vicious circle" in which each can lead to the other (Trani & Loeb, 2012). Disability also
brings extra costs of living that income-based measures miss (Mitra et al., 2017). A
systematic review of 150 studies in low- and middle-income countries found that 122 (81%)
reported a positive association between disability and a marker of poverty (Banks et al.,
2017). Studies using multidimensional measures, which count deprivations in health, education
and living standards rather than income alone, find higher deprivation among persons with
disabilities in several, though not all, countries and dimensions (Mitra et al., 2013;
Pinilla-Roncancio & Alkire, 2020; Pinilla-Roncancio et al., 2020; Trani & Loeb, 2012).

In Nigeria, evidence on disability and poverty is thin. A disability survey in Kogi and Niger
states described the circumstances of persons with disabilities in two states (Smith, 2011).
The National Bureau of Statistics (NBS) reported in its 2022 national Multidimensional Poverty
Index (MPI) that 71.4% of people in households with a person living with a disability were
multidimensionally poor, against 61.8% of people in other households (NBS, 2022, Table 7).
That comparison is unadjusted, and it uses a broad definition of disability (any difficulty,
or a skin condition such as albinism). Households that include a person with a disability may
differ from others in where they live, how old their members are and who heads them, and each
of these is linked to poverty. An unadjusted gap cannot show how much of the difference
remains once these are taken into account.

Two further problems affect studies of this kind. First, the analyst's choices (which
households to compare, which covariates to adjust for, which model to fit) can be made after
seeing the data, which inflates false positives; registering the plan in advance guards
against this (Van den Akker et al., 2021). Second, disability measures differ in their
cut-offs and in which domains they ask about, and estimates depend on those choices
(Hanass-Hancock et al., 2023; Mactaggart et al., 2021).

### Aim

This study estimates, for Nigeria in 2021–22, how much more likely people are to live in a
multidimensionally poor household when the household includes at least one member aged 5 or
older with a severe functional difficulty, compared with people in households without one
that are comparable on place, age structure and the head's characteristics.

## Methods

### Setting and design

This is a pre-registered secondary analysis of a national cross-sectional household survey.
The plan (questions, definitions, estimator, sensitivity analyses and the rule for wording
the result) was registered on the Open Science Framework ({osf}, {reg_utc}) using the
Secondary Data Preregistration template (Van den Akker et al., 2021), with the analysis code
frozen and tagged in the same commit, before the project ran any household-level analysis
linking poverty to disability. What was already known, including NBS's Table 7, is disclosed
in the registration. Deviations from the plan logged so far: {deviations}.

### Data

The NBS Multidimensional Poverty Index Survey 2021 (fieldwork 2021–22) is a nationally
representative household survey designed to measure the national MPI (NBS, 2022, 2023). The
analysis used the {nums.n("households_in_sample")} households with a completed interview. The
exploratory panel comparison used the General Household Survey-Panel (GHS-Panel), Waves 4
(2018/19) and 5 (2023/24) (NBS, 2019, 2024). Both datasets were used under licence; only
estimates from at least 30 unweighted households or people per group were published.

### Measures

**Exposure.** A household was exposed if any member aged 5 or older had "a lot of
difficulty" or "cannot do at all" in self-care, remembering or concentrating, communication,
seeing, hearing or walking. These follow the domains of the Washington Group (WG) Short Set
(Madans et al., 2011), but they are the survey's own questions, not the WG's standard measure.
The survey asks the severity of seeing, hearing and walking only of people who report a
difficulty and use glasses, a hearing aid or walking equipment. People who reported a
difficulty without an aid have no severity answer and were counted as not severe. Because aids
cost money, this misclassification probably places some people with severe difficulties from
poorer households in the comparison group, which the plan expected to bias the estimate
towards zero. Under this definition {ex["primary"]} of people lived in exposed households. NBS's
broad definition was rebuilt to check the exposure coding: the first build gave too high a
share, and the reading of NBS's footnote on assistive devices was corrected before
registration; the corrected build gave {ex["s2"]}, against NBS's published 11.0%.

**Outcome.** Multidimensional poverty was rebuilt at household level from the survey files
following the national MPI: 15 indicators in four dimensions (health, education, living
standards, and work and shocks), with a household counted as poor if its weighted deprivation
score was 26% or more (Alkire & Foster, 2011; NBS, 2022). Every member shares the household's
status. As with the exposure, the rebuild was calibrated to NBS's published figures before
registration: two education rules were corrected after a first national check failed, and
the national headcount matches partly because some indicator differences offset one another.
The rebuilt index then reproduced NBS's Table 7 within the pre-set tolerance of 2 points:
{nums.value("table7_exposed", decimals=1)}% against NBS's
{nums.value("table7_exposed_nbs", decimals=1)}% poor with a person with a disability, and
{nums.value("table7_unexposed", decimals=1)}% against
{nums.value("table7_unexposed_nbs", decimals=1)}% without.

**Covariates.** State and senatorial district; urban or rural sector; the number of household
members in seven age bands matched to the MPI's eligibility ages; and the head's sex, age and
highest education. Employment, assets, housing, shocks and schooling were not adjusted for,
because disability may change them or they form part of the outcome.

### Analysis

The estimand was the population-weighted standardised difference in the probability that a
person lives in a poor household, between exposed and unexposed households, standardised to
the population distribution of the covariates. It is interpreted only as an adjusted
association. It was estimated with double machine learning (DML; Chernozhukov et al., 2018)
using the interactive regression model in DoubleML (Bach et al., 2022), with population
weights in the score, five-fold cross-fitting repeated five times, folds formed by
enumeration area, and propensity scores clipped at 0.01 and 0.99. The outcome and propensity
models were chosen from penalised logistic regression, random forest and gradient boosting by
cross-validated loss before any exposure difference was computed, preferring the simpler
model when within one standard error of the best; this rule chose
{learner[nums.raw(f"{m}.outcome_chosen.value_text")]} for the outcome and
{learner[nums.raw(f"{m}.propensity_chosen.value_text")]} for the propensity (the lowest loss
was {learner[nums.raw(f"{m}.propensity_lowest.value_text")]}). Standard errors were clustered
by enumeration area, and p-values are from Wald z-tests. The plan fixed the smallest
difference of interest at 2 percentage points: a result would be called "no meaningful
difference" only if its whole interval lay within ±2 points.

Secondary questions (labelled as such) used the same estimator: the deprivation score (S1),
NBS's broad definition (S2), a household head with a severe difficulty (S3), each dimension's
contribution (S4), people not asked about severity counted as severe (S5), and only the
domains asked of everyone (S6). Holm's correction was applied across S1–S3. Pre-registered
checks were a survey-weighted linear probability model (Lumley, 2004), placebo exposures
permuted within district 100 times, a random added covariate, leaving out one zone at a time,
and eight robustness specifications. Sensitivity to unmeasured confounding used omitted-
variable bounds (Chernozhukov et al., 2022), sensemakr (Cinelli & Hazlett, 2020) and the
E-value (VanderWeele & Ding, 2017). Exploratory analyses estimated the difference within
sector and zone, and, in the panel, compared the change in household consumption and in work
between people whose severe difficulty began between 2018/19 and 2023/24 and people without
onset, by weighted least squares with clustered errors, run only if the minimum detectable
difference was at most half a standard deviation.

All analysis code, the frozen plan and the published estimates are openly available
({REPO_URL}; {CODE_DOI}). The analysis code was written with the help of an AI assistant
(Claude, Anthropic), under the author's direction; every analytic decision was fixed in the
registered plan, and the code was tested on synthetic data before the real run. The online
results page ({PAGE_URL}) shows every estimate as a chart made with an open-source charting
library written for this project, which builds each chart's text description from the
plotted data, checks each number in the description against the data, and gives every chart
a data table for screen-reader users; the library has not yet been evaluated by regular
screen-reader users.

### Ethical considerations

This study is a secondary analysis of anonymised data collected by NBS, whose
respondents' confidentiality is protected by the Statistics Act 2007. The data were obtained
under licence from NBS and the World Bank Microdata Library, contain no names or addresses,
and were kept on the author's computer; only estimates from at least 30 households or people
per group were published. No new data were collected and no person was contacted, so no
separate ethical approval was sought.

## Results

### Sample

Of {nums.n("households_in_sample")} households, {n_excluded:,} were excluded:
{nums.n("missing_poor_households")} with missing poverty data
({nums.share("missing_poor_share")} of people) and
{nums.n("missing_exposure_primary_households")} with missing disability answers
({nums.share("missing_exposure_primary_share")} of people){both}. The primary analysis
included {nums.n("weights_n")} households, of which {nums.count("estimates.primary.n_exposed")}
were exposed (Kish effective sample size {nums.n("kish_effective_n")}). Exposure was rare: the
median estimated propensity among exposed households was
{nums.value("quantile_exposed_q50", decimals=2)}, and the propensity was clipped for
{nums.share("overlap_clipped_share_weighted")} of people.

Table 1 describes the two groups; it was added after registration and is descriptive only.
Exposed households were larger ({t1m("household members, all ages")} against
{t1m("household members, all ages", "unexposed")} members on average) and had more members
aged 70 or over ({t1m("members aged 70+")} against {t1m("members aged 70+", "unexposed")}).
Their head was more often aged 60 or over ({t1("head_age", "60+")} against
{t1("head_age", "60+", "unexposed")}), female ({t1("head_sex", "female")} against
{t1("head_sex", "female", "unexposed")}) or without education ({t1("head_education", "none")}
against {t1("head_education", "none", "unexposed")}), and they lived more often in the North
West and South South zones.

### Main result

People in households with a member aged 5 or older with a severe difficulty were
{nums.est("primary")} percentage points more likely to be multidimensionally poor than people
in comparable households (95% CI {nums.ci("primary")}; {pval(nums, "estimates.primary.pval")};
Table 2). {text.comparison_rates(nums)} The risk ratio was {nums.value("evalue_rr")}
({nums.value("evalue_rr_ci_low")} to {nums.value("evalue_rr_ci_high")}; this interval treats
the comparison rate as fixed). The whole interval lies above the smallest difference of
interest. In the households where the comparison is better supported (estimated propensity
between 0.01 and 0.99, {nums.num("derived.share_inside_overlap")}% of people, of whom
{nums.num("estimates.overlap_population.mu0")}% were poor without exposure), the difference
was {nums.est("overlap_population")} points ({nums.ci("overlap_population")}). This is a
different population from the primary one, not a correction of it.

All three Holm-corrected secondary results were supported: the deprivation score was
{nums.est("s1_score")} points higher out of 100 (S1), and the difference was
{nums.est("s2_broad")} points under NBS's broad definition (S2) and {nums.est("s3_head")}
points when the head had the difficulty (S3). Restricting exposure to the domains asked of
everyone (S6) gave {nums.est("s6_routing_free")} points ({nums.ci("s6_routing_free")}). Counting
people not asked about severity as severe (S5) gave a smaller difference,
{nums.est("s5_unasked_severe")} points. Of the four dimensions, the difference lay mostly in
health ({nums.est("s4_health")} points of the deprivation score) and work and shocks
({nums.est("s4_work_and_shocks")}), with intervals for education and living standards that
include zero (S4).

### Checks

The survey-weighted linear model gave a lower estimate, {nums.est("survey_lpm")} points
({nums.ci("survey_lpm")}); it assumes a linear, additive relation with the covariates, which
the flexible learners do not. Other learners and adjustment sets gave
{nums.num("derived.robustness.min")} to {nums.num("derived.robustness.max")} points, and
leaving out one zone at a time {nums.num("derived.leave_one_zone_out.min")} to
{nums.num("derived.leave_one_zone_out.max")} (Table 3). The
{nums.value("placebo_n", decimals=0)} placebo estimates averaged {pts("placebo_mean", 1)}
points (standard deviation {pts("placebo_sd", 1)}); none was as far from zero as the real
estimate (empirical p = {apa_p("placebo_empirical_p")}). Of their intervals,
{nums.share("placebo_share_ci_excluding_0", decimals=0)} excluded zero, against about 5%
expected; with 100 draws this is within chance, but the standard errors, which ignore the
strata, may be slightly too small. Adding a random covariate moved the estimate by
{pts("rcc_moved", 1)} points, within the pre-set allowance of {pts("rcc_allowed", 1)} points
(the range across fold splits), a weak check.

### Sensitivity to unmeasured confounding

In the worst case, an unmeasured factor aligned perfectly with both poverty and exposure,
and accounting for {nums.share("rv")} of what is left unexplained in each, could bring the
estimate to zero (Table 4). This is far weaker than the measured covariates: place, for
example, accounts for {nums.share("bench_place_cf_y")} (poverty) and {nums.share("bench_place_cf_d")} (exposure).
A factor as strong as the head's education, place or sector, and aligned with poverty and
exposure as each of those is, would move the estimate only to between
{nums.num("derived.benchmarks.min")} and {nums.num("derived.benchmarks.max")} points; those
alignments are weak, so these bounds are narrow. In the linear sensemakr model, a factor three
times as strong as the head's education would bring the estimate to {nums.est("sensemakr_3x")}
points ({nums.ci("sensemakr_3x")}). The E-value was {nums.value("evalue", decimals=1)}
({nums.value("evalue_ci", decimals=1)} for the confidence limit, which ignores uncertainty in
the comparison rate). With a base rate of about 60%, the risk ratio cannot exceed about
{nums.num("derived.rr_ceiling", 1, 1)}, so E-values are small by construction here.

### Exploratory analyses

The difference was larger in urban ({nums.est("x1_sector_urban")} points,
{nums.ci("x1_sector_urban")}) than rural areas ({nums.est("x1_sector_rural")},
{nums.ci("x1_sector_rural")}); zone estimates varied and were imprecise (Table 5). No
interaction was tested. In the panel, {ghs_line} Those lost to follow-up were younger (mean
age {nums.value("attrition_age_attriters", "ghs", 1)} against
{nums.value("attrition_age_stayers", "ghs", 1)} years) and more often had a severe difficulty
in 2018/19 ({nums.share("attrition_severe_w4_attriters", "ghs")} against
{nums.share("attrition_severe_w4_stayers", "ghs")}). With complete work answers,
{nums.n("dwork_n", "ghs")} people ({nums.n("dwork_onset_cases", "ghs")} with onset) were
compared: the share who worked fell by more, or rose by less, among people with onset, a
difference of {nums.est("ghs_dwork")} percentage points (95% CI {nums.ci("ghs_dwork")}). The
interval for the change in log consumption, {nums.est("ghs_dlog_consumption", decimals=2)}
({nums.ci("ghs_dlog_consumption", 2)}), includes zero, but the comparison could detect only
differences of about {nums.num(sv("dlog_consumption_mde", "ghs"), 1, 2)} log points or more
(design effect {nums.value("dlog_consumption_deff", "ghs", 1)}), so it cannot rule out a
moderate difference.

## Discussion

In Nigeria in 2021–22, people living with a household member who has a severe functional
difficulty were about {nums.num("derived.relative_increase", 100, 0)}% more likely, in
relative terms, to be multidimensionally poor than people in comparable households, an
adjusted association. Under NBS's broad definition, the adjusted difference
({nums.est("s2_broad")} points) was lower than the unadjusted gap (NBS:
{nums.value("table7_gap_nbs", decimals=1)} points; this rebuild:
{nums.value("table7_gap", decimals=1)}), though its interval includes the unadjusted gap and
the two are different quantities. The narrower, severe definition gave a larger difference.
The direction agrees with studies that found higher multidimensional poverty among persons
with disabilities in several countries (Mitra et al., 2013; Pinilla-Roncancio & Alkire, 2020).
The difference lay mostly in the health and the work-and-shocks dimensions, as in NBS's own
description of these households (NBS, 2022); health also contributed most in a case-control
study in three countries (Pinilla-Roncancio et al., 2020). These dimensions are where
disability-related needs and lost work would be expected to appear. The panel's fall in work
among people with onset is exploratory: within a five-year gap, stopping work may come before
the reported difficulty as well as after it, and the work questions were worded differently
in the two rounds.

The secondary results bear on the measurement problem. Restricting exposure to self-care,
remembering and communication, which every member was asked, gave a difference close to the
primary, which is consistent with the result not resting on the aid-dependent questions.
Counting people not asked about severity as severe did not raise the estimate as the plan
expected; it lowered it. Those people answered only a yes/no question that does not separate
some from a lot of difficulty, so the group probably includes many milder cases, which would
dilute the difference. The plan's description of the primary and S5 estimates as two bounds
therefore did not hold.

The study has four strengths. The plan, including the wording of the result, was registered
before the project linked poverty to disability in any household data, and no deviation was
needed. After calibration, the rebuilt poverty measure reproduced NBS's published comparison
within the pre-set tolerance. The flexible estimator does not rest on one model, and the
result held across learners, adjustment sets and when any one zone was left out, although
the linear model and the overlap population gave lower estimates. All code and published
estimates are open, so the analysis can be re-run by anyone with licensed access to the
survey.

### Conclusions

Multidimensional poverty in Nigeria is more common in households that include a person with
a severe functional difficulty than in comparable households, after accounting for where
they live, their age structure and the head's characteristics. This is an adjusted
association.

### Implications

Recording disability in poverty programmes and the national social register, for example
with the WG questions, could help these households be found and reached; this study did not
assess how well such questions would target them. Future NBS surveys could ask the WG Short
Set of every member aged 5 and over, rather than asking severity only of aid users, which
would remove the main measurement gap in this survey. Because the result is an association,
it shows where poverty is more common, not what would follow from preventing or supporting
disability; policies need their own evaluations.

### Limitations

This is **an adjusted association, not a causal effect**, for two reasons. Earlier poverty
can lead to disability and also goes with poverty today, and a single cross-section cannot
order them. Religion, ethnicity, conflict, local health services and earlier poverty were
not measured; a factor aligned with poverty and exposure as the measured ones are would leave
a clear difference, but a factor much weaker than place, if aligned with both, could remove
it. Exposure was rare and the primary estimate relies partly on clipped propensities. The
disability questions are not the WG standard, and the routing misclassifies some people.
Household composition may itself respond to disability. The survey design's strata are not
distributed and were approximated. Holm's correction covered only S1–S3; the subgroup and
panel analyses are exploratory, the panel has two waves, lost younger people and people with
difficulties more often, and its comparison assumes the two groups would otherwise have
changed alike. Like the national MPI, the measure ignores the extra costs of disability, so
it may understate deprivation in exposed households (Mitra et al., 2017)."""

    tables = f"""{table1_md(table)}

**Table 2.** Primary and secondary estimates: difference in the share of people who are
multidimensionally poor (percentage points; S1 and S4 on the 0–100 deprivation score),
exposed versus comparable unexposed households, Nigeria MPI Survey 2021.

| Estimate | Exposed households (n) | Difference | 95% CI | p |
|---|---|---|---|---|
{row(nums, "primary", "Primary: member aged 5+ with a severe difficulty")}
{row(nums, "overlap_population", "Primary, overlap population (secondary)")}
{row(nums, "s1_score", "S1: deprivation score")}
{row(nums, "s2_broad", "S2: NBS broad definition")}
{row(nums, "s3_head", "S3: household head")}
{row(nums, "s5_unasked_severe", "S5: not asked about severity counted as severe")}
{row(nums, "s6_routing_free", "S6: self-care, remembering, communication only")}
{row(nums, "s4_health", "S4: health")}
{row(nums, "s4_education", "S4: education")}
{row(nums, "s4_living_standards", "S4: living standards")}
{row(nums, "s4_work_and_shocks", "S4: work and shocks")}

*Note:* Population-weighted DML; standard errors clustered by enumeration area; p-values from
Wald z-tests. Holm-corrected p-values (S1–S3): S1 {pval(nums, "estimates.s1_score.holm_p")},
S2 {pval(nums, "estimates.s2_broad.holm_p")}, S3 {pval(nums, "estimates.s3_head.holm_p")}.
S4–S6 are descriptive and unadjusted for multiplicity. Exposed counts differ slightly between
rows because each outcome or definition has its own missing answers.

**Table 3.** Robustness and refutation checks of the primary estimate (percentage points).

| Specification | Exposed households (n) | Difference | 95% CI |
|---|---|---|---|
{row(nums, "survey_lpm", "Survey-weighted linear probability model", p=False)}
{row(nums, "rob_learners_logistic", p=False)}
{row(nums, "rob_learners_forest", p=False)}
{row(nums, "rob_learners_boosting", p=False)}
{row(nums, "rob_no_head_education", p=False)}
{row(nums, "rob_place_head_sex_age", p=False)}
{row(nums, "rob_state_only_place", p=False)}
{row(nums, "rob_outcome_poor_fuel_alt", p=False)}
{row(nums, "rob_outcome_poor_shock_dk0", p=False)}
{row(nums, "lozo_north_central", p=False)}
{row(nums, "lozo_north_east", p=False)}
{row(nums, "lozo_north_west", p=False)}
{row(nums, "lozo_south_east", p=False)}
{row(nums, "lozo_south_south", p=False)}
{row(nums, "lozo_south_west", p=False)}

*Note:* Robustness and leave-one-zone-out runs use one cross-fitting repetition.

**Table 4.** Sensitivity of the primary estimate to unmeasured confounding.

| Measure | Value |
|---|---|
| Robustness value, estimate to zero (RV; worst-case alignment) | {nums.share("rv")} |
| Robustness value, interval to include zero (RVa) | {nums.share("rva", decimals=1)} |
| Head's education: strength with poverty / exposure | {nums.share("bench_head_education_cf_y")} / {nums.share("bench_head_education_cf_d")} |
| Head's education: bounds at its estimated alignment (points) | {pts("bench_head_education_theta_lower")} to {pts("bench_head_education_theta_upper")} |
| Place (state and district): strength with poverty / exposure | {nums.share("bench_place_cf_y")} / {nums.share("bench_place_cf_d")} |
| Place: bounds at its estimated alignment (points) | {pts("bench_place_theta_lower")} to {pts("bench_place_theta_upper")} |
| Sector: strength with poverty / exposure | {nums.share("bench_sector_cf_y")} / {nums.share("bench_sector_cf_d")} |
| Sector: bounds at its estimated alignment (points) | {pts("bench_sector_theta_lower")} to {pts("bench_sector_theta_upper")} |
| sensemakr, 1× head's education (points, 95% CI) | {nums.est("sensemakr_1x")} ({nums.ci("sensemakr_1x")}) |
| sensemakr, 2× head's education | {nums.est("sensemakr_2x")} ({nums.ci("sensemakr_2x")}) |
| sensemakr, 3× head's education | {nums.est("sensemakr_3x")} ({nums.ci("sensemakr_3x")}) |
| E-value, estimate / confidence limit | {nums.value("evalue", decimals=1)} / {nums.value("evalue_ci", decimals=1)} |

*Note:* Strengths and bounds from DoubleML's omitted-variable analysis (Chernozhukov et al.,
2022); the benchmark refits use the project's own code, which follows DoubleML's
`sensitivity_benchmark` but rebuilds the learners for the shorter set of covariates. The
sensemakr model is a weighted linear model that ignores the survey design. The E-value for
the confidence limit ignores uncertainty in the comparison rate.

**Table 5.** Exploratory estimates (percentage points; GHS-Panel consumption in log points).

| Estimate | Exposed / onset (n) | Difference | 95% CI |
|---|---|---|---|
{row(nums, "x1_sector_urban", "Urban", p=False)}
{row(nums, "x1_sector_rural", "Rural", p=False)}
{row(nums, "x1_zone_north_central", "North Central", p=False)}
{row(nums, "x1_zone_north_east", "North East", p=False)}
{row(nums, "x1_zone_north_west", "North West", p=False)}
{row(nums, "x1_zone_south_east", "South East", p=False)}
{row(nums, "x1_zone_south_south", "South South", p=False)}
{row(nums, "x1_zone_south_west", "South West", p=False)}
| GHS-Panel: change in work, onset vs no onset (n = {nums.n("dwork_n", "ghs")}) | {nums.n("dwork_onset_cases", "ghs")} | {nums.est("ghs_dwork")} | {nums.ci("ghs_dwork")} |
| GHS-Panel: change in log consumption per person (n = {nums.n("dlog_consumption_n", "ghs")}) | {nums.n("dlog_consumption_onset_cases", "ghs")} | {nums.est("ghs_dlog_consumption", decimals=2)} | {nums.ci("ghs_dlog_consumption", 2)} |

*Note:* Exploratory: no multiplicity adjustment and no interaction test. GHS-Panel: people
aged 15 and over without a severe difficulty in 2018/19, longitudinal weights."""

    return f"""---
title: "Household disability and multidimensional poverty in Nigeria: a pre-registered secondary analysis"
running-title: "Disability and poverty in Nigeria"
lang: en-GB
---

**Running title:** Disability and poverty in Nigeria

## Abstract

{abstract}

**Keywords:** {keywords}

{BODY_START}

{body}

{BODY_END}

## Acknowledgements

The National Bureau of Statistics and the World Bank
Microdata Library provided the survey data. The first draft of this manuscript was generated
with Claude (Claude Opus 5.5, Anthropic) from the registered plan and the published
estimates; every number in the text and tables is inserted by a script from the published
results file. The author reviewed and edited the text, and checked that every reference
exists and supports the statement it is cited for.

**Competing interests:** The author declares that they have no competing interests.

**Funding:** This research received no specific grant from any funding agency in the public,
commercial or not-for-profit sectors.

**Data availability:** The survey microdata are available from NBS and the World Bank
Microdata Library under their licences and cannot be redistributed. All published estimates,
the analysis code and the registered plan are openly available ({REPO_URL}; {CODE_DOI};
{osf}).

## References

{{REFERENCES}}

## Tables

{tables}
"""


ACCESS = "Accessed 10 November 2026."

REFERENCES = f"""Alkire, S., & Foster, J. (2011). Counting and multidimensional poverty measurement.
*Journal of Public Economics, 95*(7–8), 476–487. https://doi.org/10.1016/j.jpubeco.2010.11.006

Bach, P., Chernozhukov, V., Kurz, M. S., & Spindler, M. (2022). DoubleML – An object-oriented
implementation of double machine learning in Python. *Journal of Machine Learning Research,
23*(53), 1–6. https://jmlr.org/papers/v23/21-0862.html {ACCESS}

Banks, L. M., Kuper, H., & Polack, S. (2017). Poverty and disability in low- and
middle-income countries: A systematic review. *PLOS ONE, 12*(12), e0189996.
https://doi.org/10.1371/journal.pone.0189996

Chernozhukov, V., Chetverikov, D., Demirer, M., Duflo, E., Hansen, C., Newey, W., & Robins,
J. (2018). Double/debiased machine learning for treatment and structural parameters. *The
Econometrics Journal, 21*(1), C1–C68. https://doi.org/10.1111/ectj.12097

Chernozhukov, V., Cinelli, C., Newey, W., Sharma, A., & Syrgkanis, V. (2022). *Long story
short: Omitted variable bias in causal machine learning* (NBER Working Paper No. 30302).
National Bureau of Economic Research. https://doi.org/10.3386/w30302

Cinelli, C., & Hazlett, C. (2020). Making sense of sensitivity: Extending omitted variable
bias. *Journal of the Royal Statistical Society: Series B (Statistical Methodology), 82*(1),
39–67. https://doi.org/10.1111/rssb.12348

Groce, N., Kett, M., Lang, R., & Trani, J.-F. (2011). Disability and poverty: The need for a
more nuanced understanding of implications for development policy and practice. *Third World
Quarterly, 32*(8), 1493–1513. https://doi.org/10.1080/01436597.2011.604520

Hanass-Hancock, J., Kamalakannan, S., Murthy, G. V. S., Palmer, M., Pinilla-Roncancio, M.,
Rivas Velarde, M., Tetali, S., & Mitra, S. (2023). What cut-off(s) to use with the
Washington Group short set of questions? *Disability and Health Journal, 16*(4), 101499.
https://doi.org/10.1016/j.dhjo.2023.101499

Lumley, T. (2004). Analysis of complex survey samples. *Journal of Statistical Software,
9*(8), 1–19. https://doi.org/10.18637/jss.v009.i08

Mactaggart, I., Hasan Bek, A., Banks, L. M., Bright, T., Dionicio, C., Hameed, S., Neupane,
S., Murthy, G. V. S., Orucu, A., Oye, J., Naber, J., Shakespeare, T., Patterson, A., Polack,
S., & Kuper, H. (2021). Interrogating and reflecting on disability prevalence data collected
using the Washington Group tools: Results from population-based surveys in Cameroon,
Guatemala, India, Maldives, Nepal, Turkey and Vanuatu. *International Journal of
Environmental Research and Public Health, 18*(17), 9213.
https://doi.org/10.3390/ijerph18179213

Madans, J. H., Loeb, M. E., & Altman, B. M. (2011). Measuring disability and monitoring the
UN Convention on the Rights of Persons with Disabilities: The work of the Washington Group on
Disability Statistics. *BMC Public Health, 11*(Suppl 4), S4.
https://doi.org/10.1186/1471-2458-11-S4-S4

Mitra, S., Palmer, M., Kim, H., Mont, D., & Groce, N. (2017). Extra costs of living with a
disability: A review and agenda for research. *Disability and Health Journal, 10*(4),
475–484. https://doi.org/10.1016/j.dhjo.2017.04.007

Mitra, S., Posarac, A., & Vick, B. (2013). Disability and poverty in developing countries: A
multidimensional study. *World Development, 41*, 1–18.
https://doi.org/10.1016/j.worlddev.2012.05.024

National Bureau of Statistics. (2019). *General Household Survey, Panel (GHS-Panel)
2018–2019* (NGA_2018_GHSP-W4_v03_M) [Data set]. World Bank Microdata Library.
https://microdata.worldbank.org/index.php/catalog/3557 Downloaded 16 October 2026.

National Bureau of Statistics. (2022). *Nigeria Multidimensional Poverty Index (2022)*.
https://ophi.org.uk/sites/default/files/2024-05/Nigeria_MPI_2022_report.pdf {ACCESS}

National Bureau of Statistics. (2023). *Multidimentional Poverty index Survey 2021 v1.0*
[sic] (NGA-NBS-MPI-2021-v1.0; public use, April 2023) [Data set]. National Data Archive.
https://microdata.nigerianstat.gov.ng/index.php/catalog/71 Downloaded 16 October 2026.

National Bureau of Statistics. (2024). *Nigeria General Household Survey, Panel
(GHS-Panel) Wave 5 2023–2024* (NGA_2023_GHSP-W5_v02_M) [Data set]. World Bank Microdata
Library. https://microdata.worldbank.org/index.php/catalog/6410 Downloaded 16 October 2026.

Palmer, M. (2011). Disability and poverty: A conceptual review. *Journal of Disability Policy
Studies, 21*(4), 210–218. https://doi.org/10.1177/1044207310389333

Pinilla-Roncancio, M., & Alkire, S. (2020). How poor are people with disabilities? Evidence
based on the global multidimensional poverty index. *Journal of Disability Policy Studies,
31*(4), 206–216. https://doi.org/10.1177/1044207320919942

Pinilla-Roncancio, M., Mactaggart, I., Kuper, H., Dionicio, C., Naber, J., Murthy, G. V. S.,
& Polack, S. (2020). Multidimensional poverty and disability: A case control study in India,
Cameroon, and Guatemala. *SSM – Population Health, 11*, 100591.
https://doi.org/10.1016/j.ssmph.2020.100591

Smith, N. (2011). The face of disability in Nigeria: A disability survey in Kogi and Niger
States. *Disability, CBR & Inclusive Development, 22*(1), 35–47.
https://doi.org/10.5463/dcid.v22i1.11

Trani, J.-F., & Loeb, M. (2012). Poverty and disability: A vicious circle? Evidence from
Afghanistan and Zambia. *Journal of International Development, 24*(S1), S19–S52.
https://doi.org/10.1002/jid.1709

Van den Akker, O. R., Weston, S., Campbell, L., Chopik, B., Damian, R., Davis-Kean, P., Hall,
A., Kosie, J., Kruse, E., Olsen, J., Ritchie, S., Valentine, K. D., Van 't Veer, A., &
Bakker, M. (2021). Preregistration of secondary data analysis: A template and tutorial.
*Meta-Psychology, 5*. https://doi.org/10.15626/MP.2020.2625

VanderWeele, T. J., & Ding, P. (2017). Sensitivity analysis in observational research:
Introducing the E-value. *Annals of Internal Medicine, 167*(4), 268–274.
https://doi.org/10.7326/M16-2607"""


def body_words(md: str) -> int:
    """Words in the main text (between the body markers), as a word processor counts them."""
    body = md.split(BODY_START, 1)[1].split(BODY_END, 1)[0]
    body = re.sub(r"^#+\s*", "", body, flags=re.M)
    return len(re.findall(r"\S+", body.replace("**", "")))


def abstract_words(md: str) -> int:
    part = md.split("## Abstract", 1)[1].split("**Keywords:**", 1)[0]
    return len(re.findall(r"\S+", part.replace("**", "")))


def build(payload: Mapping[str, Any], table1_rows: list[dict[str, str]] | None = None) -> str:
    rows = load_table1() if table1_rows is None else table1_rows
    out = manuscript_md(payload, rows).replace("{REFERENCES}", REFERENCES)
    if re.search(r"\{[A-Za-z_.]+\}", out):
        raise ValueError("an unfilled placeholder is left in the text")
    out = out.replace("\n\n\n", "\n\n")
    bad = text.forbidden(out)
    if bad:
        raise ValueError(f"wording the pre-registration rules out: {sorted(set(bad))}")
    if (n := body_words(out)) > WORD_LIMIT:
        raise ValueError(f"main text has {n} words; the limit is {WORD_LIMIT}")
    if (n := abstract_words(out)) > ABSTRACT_LIMIT:
        raise ValueError(f"abstract has {n} words; the limit is {ABSTRACT_LIMIT}")
    return out


WITHHELD = "[link withheld for blind review]"
IDENTIFYING = (
    re.compile(r"https://osf\.io/\S+?(?=[);,\s])"),
    re.compile(r"https://(?:github\.com|batestguy\.github\.io)/\S+?(?=[);,\s])"),
    re.compile(r"https://doi\.org/10\.5281/zenodo\.\S+?(?=[);,\s])"),
)


def blind(md: str) -> str:
    """The copy for review: links that name the author or the project are withheld."""
    for pattern in IDENTIFYING:
        md = pattern.sub(WITHHELD, md)
    if re.search(r"batestguy|osf\.io|zenodo|curb.?cut", md, re.I):
        raise ValueError("the blinded copy still identifies the author")
    return md


def reference_doc(pandoc: str, out_dir: Path) -> Path:
    """pandoc's default Word template with the journal's layout: double spacing, 12-point
    text and continuous line numbers (made fresh each run, so no binary is committed)."""
    ref = out_dir / "reference.docx"
    with ref.open("wb") as fh:
        subprocess.run(
            [pandoc, "--print-default-data-file", "reference.docx"], check=True, stdout=fh
        )
    with zipfile.ZipFile(ref) as zin:
        parts = {name: zin.read(name) for name in zin.namelist()}
    styles = parts["word/styles.xml"].decode("utf-8")
    styles, n_p = re.subn(
        r"<w:pPrDefault>.*?</w:pPrDefault>",
        '<w:pPrDefault><w:pPr><w:spacing w:after="0" w:line="480" w:lineRule="auto"/>'
        "</w:pPr></w:pPrDefault>",
        styles,
        count=1,
        flags=re.S,
    )
    styles = re.sub(
        r'(<w:rPrDefault>.*?<w:sz w:val=")\d+(")', r"\g<1>24\g<2>", styles, count=1, flags=re.S
    )
    document = parts["word/document.xml"].decode("utf-8")
    document, n_s = re.subn(
        r"(<w:sectPr[^>]*>)", r'\1<w:lnNumType w:countBy="1" w:restart="continuous"/>', document
    )
    if not (n_p and n_s):
        raise ValueError("pandoc's reference.docx has changed; update reference_doc()")
    parts["word/styles.xml"] = styles.encode("utf-8")
    parts["word/document.xml"] = document.encode("utf-8")
    with zipfile.ZipFile(ref, "w", zipfile.ZIP_DEFLATED) as zout:
        for name, data in parts.items():
            zout.writestr(name, data)
    return ref


def to_docx(md_text: str, out: Path, pandoc: str) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    src = out.with_suffix(".md")
    src.write_text(md_text, encoding="utf-8", newline="\n")
    ref = reference_doc(pandoc, out.parent)
    subprocess.run(
        [
            pandoc,
            str(src),
            "--from",
            "markdown",
            "--to",
            "docx",
            "--reference-doc",
            str(ref),
            "--output",
            str(out),
        ],
        check=True,
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write the P5 journal manuscript.")
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--md", type=Path, default=DEFAULT_MD)
    parser.add_argument("--table1", type=Path, default=DEFAULT_TABLE1)
    parser.add_argument("--docx", action="store_true", help="also write Word files (pandoc)")
    parser.add_argument("--out-dir", type=Path, default=OUT_DIR)
    parser.add_argument("--pandoc", default=os.environ.get("PANDOC", DEFAULT_PANDOC))
    parser.add_argument("--check", action="store_true", help="fail if the committed md differs")
    args = parser.parse_args(argv)
    try:
        out = build(json.loads(args.data.read_text(encoding="utf-8")), load_table1(args.table1))
    except (ValueError, KeyError) as error:
        print(f"Manuscript failed: {error!r}", file=sys.stderr)
        return 1
    if args.check:
        current = args.md.read_text(encoding="utf-8") if args.md.exists() else ""
        if current != out:
            print(f"{args.md} is out of date; rerun build_manuscript.py", file=sys.stderr)
            return 1
        print(f"{args.md} matches the exported data")
        return 0
    args.md.parent.mkdir(parents=True, exist_ok=True)
    args.md.write_text(out, encoding="utf-8", newline="\n")
    print(
        f"wrote {args.md} ({body_words(out)} words in the main text, "
        f"{abstract_words(out)} in the abstract)"
    )
    if args.docx:
        to_docx(out, args.out_dir / "p5-manuscript.docx", args.pandoc)
        to_docx(blind(out), args.out_dir / "p5-manuscript-blinded.docx", args.pandoc)
        print(f"wrote {args.out_dir}/p5-manuscript.docx and p5-manuscript-blinded.docx")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
