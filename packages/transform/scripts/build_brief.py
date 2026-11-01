"""Write the P5 policy brief (``docs/brief/p5-poverty-brief.md``) from the exported data.

Run after ``export_marts.py``, from the repo root:
``uv run python packages/transform/scripts/build_brief.py [--html] [--check]``.

Every number comes from ``site/public/data/poverty.json`` through ``poverty_text.Numbers``,
with the same sentences as the poverty page (the two reasons, the misclassification note,
the registered headline wording). The brief is refused if it uses wording the
pre-registration rules out (``poverty_text.forbidden``).

* ``--check``: rebuild in memory and fail if the committed markdown differs (CI runs this
  after the export, so the brief cannot drift from the published estimates);
* ``--html``: also run pandoc (3.8; ``--pandoc`` or ``$PANDOC``) to write the standalone
  ``docs/brief/p5-poverty-brief.html`` with ``brief.css`` embedded. That file is committed;
  ``site/scripts/make-brief-pdf.mjs`` prints it to ``site/public/downloads/
  p5-poverty-brief.pdf`` with Playwright's Chromium before ``vite build`` (no LaTeX
  engine needed; CI never runs pandoc).
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from types import ModuleType
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DATA = ROOT / "site" / "public" / "data" / "poverty.json"
BRIEF_DIR = ROOT / "docs" / "brief"
DEFAULT_MD = BRIEF_DIR / "p5-poverty-brief.md"
DEFAULT_HTML = BRIEF_DIR / "p5-poverty-brief.html"
CSS = BRIEF_DIR / "brief.css"
PAGE_URL = "https://batestguy.github.io/curb-cut/poverty.html"
DEFAULT_PANDOC = "C:/Users/TOSHIBA/miniconda3/Library/bin/pandoc"


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

MONTHS = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)


def long_date(iso: str) -> str:
    """ "2026-11-01T09:28:07+00:00" -> "1 November 2026"."""
    year, month, day = iso[:10].split("-")
    return f"{int(day)} {MONTHS[int(month) - 1]} {year}"


def brief_md(payload: Mapping[str, Any]) -> str:
    nums = text.Numbers(payload, html_mode=False)
    if nums.raw("derived.verdict") != "higher":
        # The policy section says poverty is more common in these households; it must be
        # rewritten (by a person) before a brief with any other verdict goes out.
        raise ValueError("the brief's policy section is written for the 'higher' verdict")
    reg = "summary.mpi"
    reasons = "\n".join(
        f"{i}. {r}" for i, r in enumerate(text.reasons(nums, f"{PAGE_URL}#sensitivity-heading"), 1)
    )
    work_hi = nums.raw("estimates.ghs_dwork.ci_high")
    work_line = (
        "the share who worked went down by more, or up by less, among people whose severe "
        "difficulty began between the rounds than among comparable people without onset"
        if work_hi < 0
        else "the survey cannot show a difference in work"
    )
    cons = "estimates.ghs_dlog_consumption"
    cons_line = (
        "the interval includes zero, so the survey cannot show a difference in consumption"
        if nums.raw(f"{cons}.ci_low") <= 0 <= nums.raw(f"{cons}.ci_high")
        else "the interval does not include zero"
    )
    t7 = "passed" if nums.flag("table7_all_pass") else "failed"
    rcc = "passed" if nums.flag("rcc_pass") else "failed"
    date = long_date(str(nums.raw(f"{reg}.run_created.value_text")))
    return f"""---
title: "Disability and poverty in Nigeria"
subtitle: "Policy brief from Curb Cut. Results of {date}."
lang: en-NG
---

## Key finding

**{text.headline(nums)}** {text.comparison_rates(nums)}

Exposure is rare, so the main estimate leans on few households. Among households where the
comparison is better supported (those whose estimated chance of having such a member was
between 0.01 and 0.99, {nums.num("derived.share_inside_overlap")}% of people), the difference
is {nums.est("overlap_population")} points (95% confidence interval
{nums.ci("overlap_population")}). It is a secondary estimate, reported next to the main one.
{text.missing_line(nums)}

## What this does and does not show

This is **an adjusted association, not a causal effect**. It does not show that disability
makes households poorer. Two reasons:

{reasons}

How strong would a hidden factor need to be? Two answers to two different questions. In the
worst case, a factor lined up perfectly with both poverty and which households have such a
member, accounting for {nums.share("rv")} of what is left unexplained in each, could bring the
estimate to zero. A factor as strong as the head's education, place or urban or rural, and
lined up with poverty and exposure the way each of those is, would move it only to between
{nums.num("derived.benchmarks.min")} and {nums.num("derived.benchmarks.max")} points. On the
risk-ratio scale, the E-value is {nums.value("evalue")}.

{text.misclassification(nums)}

## How it was checked

The plan was registered publicly before any poverty figure was split by disability
({nums.text(f"{reg}.osf_url.value_text")}, {nums.text(f"{reg}.registered_utc.value_text")}),
with deviations logged so far: {nums.text(f"{reg}.deviations.value_text")}.
Our rebuilt index reproduces NBS's published comparison (Table 7:
{nums.value("table7_exposed", decimals=1)}% against NBS's
{nums.value("table7_exposed_nbs", decimals=1)}% poor with a person with a disability,
{nums.value("table7_unexposed", decimals=1)}% against
{nums.value("table7_unexposed_nbs", decimals=1)}% without; the check {t7}). Eight other
reasonable choices give {nums.num("derived.robustness.min")} to
{nums.num("derived.robustness.max")} points; leaving out one zone at a time gives
{nums.num("derived.leave_one_zone_out.min")} to {nums.num("derived.leave_one_zone_out.max")}.
Shuffling exposure {nums.value("placebo_n", decimals=0)} times gave estimates centred near zero.
A random extra factor moved the one-repetition estimate by
{nums.num("summary.mpi.rcc_moved.value", 100, 2)} points, within the
{nums.num("summary.mpi.rcc_allowed.value", 100, 2)} points that the fold split alone moves it
(check {rcc}). A survey-weighted linear model gives {nums.est("survey_lpm")} points
({nums.ci("survey_lpm")}).

## Other registered results

- NBS's broad definition (S2): {nums.est("s2_broad")} points ({nums.ci("s2_broad")}). The
  household head has the difficulty (S3): {nums.est("s3_head")} points ({nums.ci("s3_head")}).
- Where the difference sits (S4, points out of 100 on the deprivation score): health
  {nums.est("s4_health")} ({nums.ci("s4_health")}), work and shocks
  {nums.est("s4_work_and_shocks")} ({nums.ci("s4_work_and_shocks")}), education
  {nums.est("s4_education")} ({nums.ci("s4_education")}), living standards
  {nums.est("s4_living_standards")} ({nums.ci("s4_living_standards")}). Descriptive only.
- **Exploratory** (the same people in 2018/19 and 2023/24, General Household Survey-Panel):
  of {nums.n("w4_people_15plus", "ghs")} people aged 15 and over in 2018/19,
  {nums.n("found_in_w5", "ghs")} were found again; {nums.n("analysis_sample", "ghs")} had no
  severe difficulty in 2018/19 and complete answers, and {nums.n("onset_cases", "ghs")} of
  them had one by 2023/24. Work: {nums.est("ghs_dwork")} percentage
  points ({nums.ci("ghs_dwork")}): {work_line}. Consumption:
  {nums.est("ghs_dlog_consumption", decimals=3)} log points
  ({nums.ci("ghs_dlog_consumption", 3)}): {cons_line}. Two rounds only; the comparison
  assumes the two groups would otherwise have changed alike, which cannot be tested, and the
  communication and work questions are worded differently in the two rounds.

## What this suggests for policy

- **Find these households.** Multidimensional poverty is more common in households with a
  severely disabled member (an adjusted association). Poverty programmes and social
  registers can record disability, with the Washington Group questions, so that these
  households can be reached.
- **Ask everyone the severity questions.** MPI 2021 asked how hard seeing, hearing or walking
  is only of people who use an aid. Asking the Washington Group Short Set of every member
  aged 5 and over would close the main measurement gap in this survey.
- **Read the number as a description.** It shows where poverty is concentrated, not what
  would happen if disability were prevented or supported. Policies should be judged on their
  own evaluations.

## Data, registration and citations

- Full results, checks and explanations: {PAGE_URL}
- Pre-registration: {nums.text(f"{reg}.osf_url.value_text")} (frozen at tag
  {nums.text(f"{reg}.freeze_tag.value_text")}, commit
  {nums.text(f"{reg}.freeze_commit.value_text")}).
- National Bureau of Statistics, Multidimensional Poverty Index Survey 2021, v1.0
  (NGA-NBS-MPI-2021-v1.0); NBS, Nigeria Multidimensional Poverty Index (2022), Table 7.
  Aggregated reporting only; a copy of this brief goes to the National Data Archive.
- NBS and the World Bank, General Household Survey-Panel, Waves 4 (NGA_2018_GHSP-W4_v03_M)
  and 5 (NGA_2023_GHSP-W5_v02_M), World Bank Microdata Library.
- Curb Cut's disability prevalence figures elsewhere use the Nigeria Demographic and Health
  Survey 2024 (National Population Commission and ICF, The DHS Program); no DHS data are used
  in this brief.
- Only estimates that passed a disclosure check (at least 30 households or people in each
  group; the smallest group behind any published estimate has
  {nums.count("derived.smallest_group")} households or people) are published.
"""


def build(payload: Mapping[str, Any]) -> str:
    out = brief_md(payload)
    bad = text.forbidden(out)
    if bad:
        raise ValueError(f"wording the pre-registration rules out: {sorted(set(bad))}")
    return out


SOURCE_STAMP = "source markdown sha256:"


def md_sha256(text_: str) -> str:
    return hashlib.sha256(text_.encode("utf-8")).hexdigest()


def html_matches(md_text: str, html_path: Path) -> bool:
    """Whether the committed HTML was made from this markdown (its stamp)."""
    if not html_path.exists():
        return False
    return f"<!-- {SOURCE_STAMP} {md_sha256(md_text)} -->" in html_path.read_text(encoding="utf-8")


def to_html(md: Path, html: Path, pandoc: str) -> None:
    subprocess.run(
        [
            pandoc,
            str(md),
            "--from",
            "markdown",
            "--to",
            "html5",
            "--standalone",
            "--embed-resources",
            "--css",
            str(CSS),
            "--output",
            str(html),
        ],
        check=True,
    )
    # LF endings, as for every committed text file (.gitattributes), and the SHA-256 of the
    # markdown it was made from, so that --check can tell a stale HTML in CI without pandoc.
    body = html.read_text(encoding="utf-8").rstrip("\n")
    stamp = f"<!-- {SOURCE_STAMP} {md_sha256(md.read_text(encoding='utf-8'))} -->"
    html.write_text(f"{body}\n{stamp}\n", encoding="utf-8", newline="\n")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write the P5 policy brief.")
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--md", type=Path, default=DEFAULT_MD)
    parser.add_argument("--html", action="store_true", help="also run pandoc to make the HTML")
    parser.add_argument("--html-out", type=Path, default=DEFAULT_HTML)
    parser.add_argument("--pandoc", default=os.environ.get("PANDOC", DEFAULT_PANDOC))
    parser.add_argument("--check", action="store_true", help="fail if the committed md differs")
    args = parser.parse_args(argv)
    try:
        out = build(json.loads(args.data.read_text(encoding="utf-8")))
    except (ValueError, KeyError) as error:
        print(f"Brief failed: {error!r}", file=sys.stderr)
        return 1
    if args.check:
        current = args.md.read_text(encoding="utf-8") if args.md.exists() else ""
        if current != out:
            print(
                f"{args.md} is out of date with the exported data; rerun build_brief.py",
                file=sys.stderr,
            )
            return 1
        if not html_matches(out, args.html_out):
            print(
                f"{args.html_out} was not made from the current markdown; rerun with --html",
                file=sys.stderr,
            )
            return 1
        print(f"{args.md} matches the exported data, and {args.html_out.name} matches it")
        return 0
    args.md.parent.mkdir(parents=True, exist_ok=True)
    args.md.write_text(out, encoding="utf-8", newline="\n")
    print(f"wrote {args.md}")
    if args.html:
        to_html(args.md, args.html_out, args.pandoc)
        print(f"wrote {args.html_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
