"""P5: publish the registered estimates through the disclosure gate.

Run after ``p5_mpi --real`` and ``p5_ghs --real``, from the repo root:
``uv run python -I -m curbcut_ingest.restricted.p5_publish``.

Reads the two results files the analyses wrote (``data/restricted/derived/p5/results.json``
and ``ghs_results.json``: model estimates and other aggregates, never a household or a
person) and the run manifest, and writes four files through
:func:`curbcut_ingest.disclosure.publish_estimates` and :func:`~curbcut_ingest.disclosure.
publish_summary` (the gate stays the only writer to ``data/public/aggregates/``):

* ``p5_mpi_estimates.csv``: one row per MPI estimate with its 95% interval: the primary,
  the overlap population, the survey-weighted linear benchmark, S1-S6, the robustness runs,
  leave-one-zone-out, the X1 subgroups and the sensemakr bounds;
* ``p5_ghs_estimates.csv``: the two E1 estimates and R's check of each;
* ``p5_mpi_summary.csv``: scalar results: the Table 7 check, the E-value, the sensitivity
  values and benchmark bounds, the placebo summary (not its 100 estimates), the random
  common cause check, overlap, weights, the sample and its missing counts, the learner
  choice (mean losses only, not the fold losses), and the registration record from
  section 11 of ``docs/preregistration.md``;
* ``p5_ghs_summary.csv``: linkage, attrition, power and the run rule.

Estimates are proportions (0-1) or score points (0-1) as the analysis wrote them; the site
turns them into percentage points.
"""

from __future__ import annotations

import argparse
import json
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import pandas as pd

from curbcut_ingest import disclosure
from curbcut_ingest.restricted import common as c
from curbcut_ingest.restricted.p5_mpi import OUT_DIR, PREREG, registration_url

RESULTS = OUT_DIR / "results.json"
GHS_RESULTS = OUT_DIR / "ghs_results.json"
RUN_MANIFEST = OUT_DIR / "manifest.json"
DEVIATIONS = PREREG.with_name("preregistration-deviations.md")
"""Section 10's log; each deviation is a "## YYYY-MM-DD ..." heading."""

FILES = {
    "mpi_estimates": "p5_mpi_estimates.csv",
    "ghs_estimates": "p5_ghs_estimates.csv",
    "mpi_summary": "p5_mpi_summary.csv",
    "ghs_summary": "p5_ghs_summary.csv",
}

MPI = disclosure.Dataset(
    source="mpi2021",
    version="NGA-NBS-MPI-2021-v1.0",
    title="NBS Multidimensional Poverty Index Survey 2021",
    citation="National Bureau of Statistics, Multidimentional Poverty index Survey 2021 v1.0",
    terms=(
        "NBS access terms: aggregated reporting only; an electronic copy of every "
        "publication goes to the National Data Archive."
    ),
    design=(
        "P5 pre-registered analysis (docs/preregistration.md, OSF https://osf.io/kes3p/): "
        "households with a completed interview; exposure on MPI's own disability items (not "
        "the WG-SS); outcome the rebuilt MPI (k = 26%). DoubleML IRM, population weights in "
        "the score, EA-clustered standard errors. Counts are households."
    ),
)
GHS = disclosure.Dataset(
    source="ghs_w4_w5",
    version="NGA_2018_GHSP-W4_v03_M + NGA_2023_GHSP-W5_v02_M",
    title="Nigeria General Household Survey-Panel, Waves 4 (2018-2019) and 5 (2023-2024)",
    citation=(
        "National Bureau of Statistics (NBS), Nigeria. General Household Survey, Panel "
        "2018-2019, Wave 4 (NGA_2018_GHSP-W4_v03_M) and 2023-2024, Wave 5 "
        "(NGA_2023_GHSP-W5_v02_M). World Bank Microdata Library."
    ),
    terms="World Bank Microdata Library public-use terms: aggregates only, cite the dataset.",
    design=(
        "P5 exploratory E1 (pre-registration section 8): people aged 15+ in W4 linked to "
        "W5, with no severe difficulty in W4; onset = a severe WG-SS answer in W5. "
        "Change-score weighted least squares with the longitudinal weight, EA clusters. "
        "Counts are people."
    ),
)

ZONES = ("North Central", "North East", "North West", "South East", "South South", "South West")
PP = "risk difference (proportion; x100 = percentage points)"
SCORE = "difference in deprivation score (0-1; x100 = points out of 100)"

ROBUSTNESS = {
    "no_head_education": "Without the head's education",
    "place_head_sex_age": "Place and the head's sex and age only",
    "state_only_place": "Place as state only (no senatorial district)",
    "learners_logistic": "Logistic regression for both models",
    "learners_forest": "Random forest for both models",
    "learners_boosting": "Gradient boosting for both models",
    "outcome_poor_fuel_alt": "Cooking fuel without charcoal",
    "outcome_poor_shock_dk0": "Don't-know shock answers counted as not deprived",
}
SECONDARIES = {
    # name: (estimate_id, group, label, outcome, exposure, scale)
    "s1_score": (
        "s1_score",
        "secondary",
        "S1: deprivation score (0-100)",
        "score",
        "primary",
        SCORE,
    ),
    "s2_broad": (
        "s2_broad",
        "secondary",
        "S2: NBS's broad definition (some difficulty or worse, or a skin condition)",
        "poor",
        "s2",
        PP,
    ),
    "s3_head": (
        "s3_head",
        "secondary",
        "S3: the household head has a severe difficulty",
        "poor",
        "s3",
        PP,
    ),
    "s4_dim_health": ("s4_health", "dimension", "Health", "dim_health", "primary", SCORE),
    "s4_dim_education": (
        "s4_education",
        "dimension",
        "Education",
        "dim_education",
        "primary",
        SCORE,
    ),
    "s4_dim_living_standards": (
        "s4_living_standards",
        "dimension",
        "Living standards",
        "dim_living_standards",
        "primary",
        SCORE,
    ),
    "s4_dim_work_and_shocks": (
        "s4_work_and_shocks",
        "dimension",
        "Work and shocks",
        "dim_work_and_shocks",
        "primary",
        SCORE,
    ),
    "s5_unasked_severe": (
        "s5_unasked_severe",
        "secondary",
        "S5: people not asked how severe counted as severe",
        "poor",
        "s5",
        PP,
    ),
    "s6_routing_free": (
        "s6_routing_free",
        "secondary",
        "S6: self-care, remembering or communicating only",
        "poor",
        "s6",
        PP,
    ),
}


def deviations_count(text: str) -> int:
    """Dated entries ("## YYYY-MM-DD ...") in ``docs/preregistration-deviations.md``."""
    return len(re.findall(r"^## \d{4}-\d{2}-\d{2}(?!\d)", text, flags=re.M))


class PublishError(ValueError):
    """A results file lacks what the registered analysis should have written."""


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def _learners(est: Mapping[str, Any]) -> str | None:
    learners = est.get("learners")
    if not learners:
        return None
    return f"outcome {learners[0]}, exposure {learners[1]}"


def estimate_row(
    est: Mapping[str, Any],
    *,
    estimate_id: str,
    group: str,
    label: str,
    outcome: str = "poor",
    exposure: str = "primary",
    scale: str = PP,
    analysis: str = "mpi",
    holm_p: float | None = None,
    supported: bool | None = None,
) -> dict[str, Any]:
    """One row of ``p5_mpi_estimates.csv`` from a DoubleML estimate as ``p5_mpi`` wrote it."""
    if "error" in est:
        raise PublishError(f"{estimate_id}: the analysis step failed ({est['error']})")
    n = int(est["n"])
    exposed = disclosure.parse_count(est["n_exposed"])
    if exposed is None:
        raise PublishError(f"{estimate_id}: no exposed count")
    return {
        "analysis": analysis,
        "group": group,
        "estimate_id": estimate_id,
        "label": label,
        "outcome": outcome,
        "exposure": exposure,
        "scale": scale,
        "learners": _learners(est),
        "estimate": est["coef"],
        "se": est["se"],
        "ci_low": est["ci_low"],
        "ci_high": est["ci_high"],
        "pval": est.get("pval"),
        "holm_p": holm_p,
        "supported": supported,
        "mu0": est.get("mu0"),
        "n": n,
        "n_exposed": exposed,
        "n_unexposed": n - exposed,
    }


def mpi_estimates(results: Mapping[str, Any]) -> pd.DataFrame:
    """Every MPI estimate with an interval (module docstring)."""
    if results.get("status") != "complete" or results.get("failed_steps"):
        raise PublishError("results.json is not a complete run; nothing is published")
    primary = results["primary"]
    rows = [
        estimate_row(
            primary,
            estimate_id="primary",
            group="headline",
            label="All households (primary)",
        ),
        estimate_row(
            results["overlap_population"],
            estimate_id="overlap_population",
            group="headline",
            label="Households where comparison is better supported (overlap population)",
        ),
    ]
    lpm = results["r_benchmark"]["survey_lpm"]
    base = estimate_row(primary, estimate_id="_", group="_", label="_")
    rows.append(
        {
            **base,
            "group": "headline",
            "estimate_id": "survey_lpm",
            "label": "Survey-weighted linear model (benchmark)",
            "learners": None,
            "estimate": lpm["estimate"],
            "se": lpm["se"],
            "ci_low": lpm["ci_low"],
            "ci_high": lpm["ci_high"],
            "pval": None,
            "mu0": None,
        }
    )
    secondaries = results["secondaries"]
    for name, (eid, group, label, outcome, exposure, scale) in SECONDARIES.items():
        entry = secondaries[name]
        if "error" in entry:
            raise PublishError(f"{name}: the analysis step failed")
        rows.append(
            estimate_row(
                entry["estimate"],
                estimate_id=eid,
                group="headline" if eid in ("s2_broad", "s3_head") else group,
                label=label,
                outcome=outcome,
                exposure=exposure,
                scale=scale,
                holm_p=entry.get("holm_p"),
                supported=entry.get("supported"),
            )
        )
    for name, label in ROBUSTNESS.items():
        outcome = name.removeprefix("outcome_") if name.startswith("outcome_") else "poor"
        rows.append(
            estimate_row(
                results["robustness"][name],
                estimate_id=f"rob_{name}",
                group="robustness",
                label=label,
                outcome=outcome,
            )
        )
    lozo = results["refutations"]["leave_one_zone_out"]
    for zone in ZONES:
        rows.append(
            estimate_row(
                lozo[zone],
                estimate_id=f"lozo_{slug(zone)}",
                group="leave_one_zone_out",
                label=f"Without the {zone} zone",
            )
        )
    for key, est in results["x1_subgroups"].items():
        kind, _, level = key.partition("=")
        label = f"{level.capitalize()} areas" if kind == "sector" else f"{level} zone"
        rows.append(
            estimate_row(est, estimate_id=f"x1_{kind}_{slug(level)}", group="subgroup", label=label)
        )
    for bound in results["r_benchmark"]["sensemakr"]["bounds"]:
        times = bound["label"].split("x", 1)[0]
        rows.append(
            {
                **base,
                "group": "sensemakr",
                "estimate_id": f"sensemakr_{times}x",
                "label": (
                    "A hidden factor as strong as the head's education"
                    if times == "1"
                    else f"A hidden factor {times} times as strong as the head's education"
                ),
                "learners": None,
                "estimate": bound["adjusted_estimate"],
                "se": None,
                "ci_low": bound["adjusted_lower_ci"],
                "ci_high": bound["adjusted_upper_ci"],
                "pval": None,
                "mu0": None,
            }
        )
    return pd.DataFrame(rows, columns=list(disclosure.ESTIMATE_COLUMNS))


def ghs_estimates(ghs: Mapping[str, Any]) -> pd.DataFrame:
    """The two E1 estimates (only where the run rule let them run) and R's check of each."""
    labels = {
        "dlog_consumption": (
            "Change in log household consumption per person",
            "difference in the change of log consumption per person (log points)",
        ),
        "dwork": (
            "Change in whether the person worked in the last 7 days",
            "difference in the change of the share working (proportion; x100 = points)",
        ),
    }
    rows = []
    for outcome, (label, scale) in labels.items():
        result = ghs["outcomes"][outcome]
        if not result["power"]["run"]:
            continue
        onset = int(result["power"]["onset_cases"])
        for suffix, key, group in (("", "model", "e1"), ("_r", "r_check", "r_check")):
            est = result[key]
            n = int(est["n"])
            rows.append(
                {
                    "analysis": "ghs",
                    "group": group,
                    "estimate_id": f"ghs_{outcome}{suffix}",
                    "label": label if not suffix else f"{label} (R fixest check)",
                    "outcome": outcome,
                    "exposure": "onset",
                    "scale": scale,
                    "learners": None,
                    "estimate": est["estimate"],
                    "se": est["se"],
                    "ci_low": est["ci_low"],
                    "ci_high": est["ci_high"],
                    "pval": None,
                    "holm_p": None,
                    "supported": None,
                    "mu0": None,
                    "n": n,
                    "n_exposed": onset,
                    "n_unexposed": n - onset,
                }
            )
    return pd.DataFrame(rows, columns=list(disclosure.ESTIMATE_COLUMNS))


def _item(
    analysis: str,
    section: str,
    item_id: str,
    label: str,
    kind: str,
    value: Any = None,
    text: str | None = None,
) -> dict[str, Any]:
    if kind == "flag":
        value = 1.0 if value else 0.0
    return {
        "analysis": analysis,
        "section": section,
        "item_id": item_id,
        "label": label,
        "kind": kind,
        "value": value,
        "value_text": text,
    }


def registration(text: str) -> dict[str, str]:
    """Section 11 of the pre-registration: OSF URL, date, freeze tag, commit and hash."""
    url = registration_url(text)
    if url is None:
        raise PublishError("docs/preregistration.md section 11 has no OSF URL")
    found = {
        "registered_utc": re.search(r"registered (\d{4}-\d{2}-\d{2} [\d:]+ UTC)", text),
        "freeze_tag": re.search(r"tag `([^`]+)`, commit", text),
        "freeze_commit": re.search(r"commit `([0-9a-f]{40})`", text),
        "preregistration_sha256": re.search(r"`docs/preregistration\.md`: `([0-9a-f]{64})`", text),
    }
    missing = [k for k, m in found.items() if m is None]
    if missing:
        raise PublishError(f"section 11 lacks {missing}")
    out = {"osf_url": url.rstrip("/") + "/"}
    out.update({k: m.group(1) for k, m in found.items() if m is not None})
    return out


def mpi_summary(
    results: Mapping[str, Any],
    run_manifest: Mapping[str, Any],
    prereg_text: str,
    deviations_text: str = "",
) -> pd.DataFrame:
    """Scalar MPI results (module docstring). Never the fold losses or placebo estimates."""
    rows: list[dict[str, Any]] = []

    def add(section: str, item_id: str, label: str, kind: str, value: Any = None, text=None):
        rows.append(_item("mpi", section, item_id, label, kind, value, text))

    t7 = results["table7"]
    names = {
        "exposed": "People who are poor, households with a person with a disability (%)",
        "unexposed": "People who are poor, households without (%)",
        "gap": "Gap (percentage points)",
    }
    for key, name in names.items():
        add("table7", f"table7_{key}", f"Ours: {name}", "number", t7["values"][key])
        add("table7", f"table7_{key}_nbs", f"NBS Table 7: {name}", "number", t7["published"][key])
        add("table7", f"table7_{key}_pass", f"Within tolerance: {name}", "flag", t7["pass"][key])
    add("table7", "table7_tolerance", "Tolerance (points, each figure)", "number", t7["tolerance"])
    add("table7", "table7_all_pass", "Table 7 check passed", "flag", t7["all_pass"])

    ev = results["evalue"]
    for key, label in (
        ("rr", "Risk ratio"),
        ("rr_ci_low", "Risk ratio, 95% interval lower"),
        ("rr_ci_high", "Risk ratio, 95% interval upper"),
        ("evalue", "E-value for the estimate"),
        ("evalue_ci", "E-value for the interval limit closer to 1"),
    ):
        add(
            "evalue",
            f"evalue_{key}" if not key.startswith("evalue") else key,
            label,
            "number",
            ev[key],
        )

    sens = results["sensitivity"]["default"]
    add("sensitivity", "rv", "DoubleML robustness value RV", "share", sens["rv"])
    add("sensitivity", "rva", "DoubleML robustness value RVa (interval)", "share", sens["rva"])
    for which in ("lower", "upper"):
        add(
            "sensitivity",
            f"default_theta_{which}",
            f"Bound at 3% strength, {which}",
            "number",
            sens["theta"][which],
        )
        add(
            "sensitivity",
            f"default_ci_{which}",
            f"Interval at 3% strength, {which}",
            "number",
            sens["ci"][which],
        )
    add(
        "sensitivity",
        "default_cf_y",
        "Assumed strength on poverty (cf_y)",
        "share",
        sens["input"]["cf_y"],
    )
    add(
        "sensitivity",
        "default_cf_d",
        "Assumed strength on exposure (cf_d)",
        "share",
        sens["input"]["cf_d"],
    )
    for name, bench in results["sensitivity"]["benchmarks"].items():
        if "error" in bench:
            raise PublishError(f"benchmark {name} failed")
        st, b = bench["strengths"], bench["bounds"]
        for key in ("cf_y", "cf_d", "rho"):
            add("benchmark", f"bench_{name}_{key}", f"{name}: {key}", "number", st[key])
        for which in ("lower", "upper"):
            add(
                "benchmark",
                f"bench_{name}_theta_{which}",
                f"{name}: bound, {which}",
                "number",
                b["theta"][which],
            )
            add(
                "benchmark",
                f"bench_{name}_ci_{which}",
                f"{name}: interval, {which}",
                "number",
                b["ci"][which],
            )

    sm = results["r_benchmark"]["sensemakr"]
    add(
        "sensemakr",
        "sensemakr_estimate",
        "Weighted linear model estimate",
        "number",
        sm["estimate"],
    )
    add("sensemakr", "sensemakr_se", "Weighted linear model standard error", "number", sm["se"])
    add("sensemakr", "sensemakr_rv_q", "sensemakr robustness value", "share", sm["rv_q"])
    add(
        "sensemakr",
        "sensemakr_rv_qa",
        "sensemakr robustness value (interval)",
        "share",
        sm["rv_qa"],
    )
    add(
        "sensemakr",
        "sensemakr_partial_r2",
        "Partial R2 of exposure with poverty",
        "share",
        sm["partial_r2_yd_x"],
    )
    lpm = results["r_benchmark"]["survey_lpm"]
    add("sensemakr", "survey_lpm_df", "Survey linear model degrees of freedom", "number", lpm["df"])
    for key, value in results["r_benchmark"]["versions"].items():
        add("sensemakr", f"version_{key}", f"R {key} version", "text", text=str(value))

    ref = results["refutations"]
    pl = ref["placebo"]
    add("placebo", "placebo_n", "Placebo permutations", "number", pl["n"])
    add("placebo", "placebo_mean", "Placebo estimates, mean", "number", pl["mean"])
    add("placebo", "placebo_sd", "Placebo estimates, standard deviation", "number", pl["sd"])
    add(
        "placebo",
        "placebo_share_ci_excluding_0",
        "Share of placebo intervals excluding 0",
        "share",
        pl["share_ci_excluding_0"],
    )
    add(
        "placebo",
        "placebo_empirical_p",
        "Empirical p of the real estimate",
        "number",
        pl["empirical_p_real_estimate"],
    )
    rcc = ref["random_common_cause"]
    add(
        "random_common_cause",
        "rcc_reference",
        "Reference estimate (one repetition)",
        "number",
        rcc["reference"],
    )
    add(
        "random_common_cause",
        "rcc_with",
        "With a random covariate added",
        "number",
        rcc["with_random_common_cause"],
    )
    add("random_common_cause", "rcc_moved", "How far it moved", "number", rcc["moved"])
    add("random_common_cause", "rcc_allowed", "How far it may move", "number", rcc["allowed"])
    add("random_common_cause", "rcc_pass", "Random common cause check passed", "flag", rcc["pass"])
    seeds = rcc["seed_estimates"]
    add(
        "random_common_cause",
        "rcc_seed_min",
        "One repetition, five fold splits: lowest",
        "number",
        min(seeds),
    )
    add(
        "random_common_cause",
        "rcc_seed_max",
        "One repetition, five fold splits: highest",
        "number",
        max(seeds),
    )
    reps = results["primary"]["all_coef"]
    add(
        "random_common_cause",
        "primary_rep_min",
        "Primary, its repetitions: lowest",
        "number",
        min(reps),
    )
    add(
        "random_common_cause",
        "primary_rep_max",
        "Primary, its repetitions: highest",
        "number",
        max(reps),
    )

    ov = results["overlap"]
    add(
        "overlap",
        "overlap_clipped_share_weighted",
        "Share of people whose propensity was clipped",
        "share",
        ov["clipped_share"]["weighted"],
    )
    add(
        "overlap",
        "overlap_clipped_share_unweighted",
        "Share of households clipped",
        "share",
        ov["clipped_share"]["unweighted"],
    )
    out = ov["outside_overlap_population"]
    add(
        "overlap",
        "outside_households",
        "Households outside the overlap population",
        "count",
        out["households"],
    )
    add(
        "overlap",
        "outside_weighted_share",
        "Share of people outside the overlap population",
        "share",
        out["weighted_share"],
    )
    # Section 5.1: the propensity's quantiles for exposed and unexposed households (each
    # summarises hundreds of households or more; the gate checks the group counts).
    for group, q in ov["quantiles_by_exposure"].items():
        add(
            "overlap",
            f"quantile_{group}_households",
            f"{group}: households",
            "count",
            q["households"],
        )
        for key in ("q01", "q05", "q25", "q50", "q75", "q95", "q99"):
            add(
                "overlap", f"quantile_{group}_{key}", f"{group}: propensity {key}", "number", q[key]
            )
    add("overlap", "clip_low", "Clip, lower", "number", ov["range"][0])
    add("overlap", "clip_high", "Clip, upper", "number", ov["range"][1])

    w = results["weights"]
    add("sample", "weights_n", "Households in the primary analysis", "count", w["n"])
    add("sample", "kish_effective_n", "Kish effective sample size", "number", w["kish_effective_n"])
    add(
        "sample",
        "max_weight_share",
        "Largest weight's share of the total",
        "share",
        w["max_weight_share"],
    )
    s = results["sample"]
    add(
        "sample",
        "households_in_sample",
        "Households in the sample",
        "count",
        s["households_in_sample"],
    )
    for key, label in (("missing_poor", "poverty"), ("missing_exposure_primary", "exposure")):
        add(
            "sample",
            f"{key}_households",
            f"Households with {label} missing",
            "count",
            s[key]["households"],
        )
        add(
            "sample",
            f"{key}_share",
            f"Share of people with {label} missing",
            "share",
            s[key]["weighted_share_people"],
        )

    sel = results["learner_selection"]
    add("learners", "folds", "Cross-fitting folds", "number", sel["folds"])
    add("learners", "n_rep", "Repetitions", "number", results["primary"]["n_rep"])
    for model in ("outcome", "propensity"):
        add(
            "learners",
            f"{model}_chosen",
            f"Chosen {model} learner",
            "text",
            text=sel[model]["chosen"],
        )
        add(
            "learners",
            f"{model}_lowest",
            f"Lowest mean loss, {model}",
            "text",
            text=sel[model]["lowest"],
        )
        for name, cand in sel[model]["candidates"].items():
            add(
                "learners",
                f"{model}_{name}_mean_loss",
                f"{model}: {name}, mean log loss",
                "number",
                cand["mean"],
            )

    reg = registration(prereg_text)
    for key, label in (
        ("osf_url", "OSF registration"),
        ("registered_utc", "Registered (UTC)"),
        ("freeze_tag", "Code freeze tag"),
        ("freeze_commit", "Code freeze commit"),
        ("preregistration_sha256", "SHA-256 of the pre-registration at the freeze"),
    ):
        add("registration", key, label, "text", text=reg[key])
    count = deviations_count(deviations_text)
    add(
        "registration",
        "deviations",
        "Deviations logged",
        "text",
        text="none" if count == 0 else str(count),
    )
    git = run_manifest.get("git", {})
    if git.get("dirty"):
        raise PublishError("the real run was made from a dirty working tree")
    add(
        "registration",
        "run_commit",
        "Commit the real run was made from",
        "text",
        text=str(git.get("commit")),
    )
    add(
        "registration",
        "run_created",
        "Real run finished (UTC)",
        "text",
        text=str(run_manifest.get("created")),
    )
    return pd.DataFrame(rows, columns=list(disclosure.SUMMARY_COLUMNS))


def ghs_summary(ghs: Mapping[str, Any]) -> pd.DataFrame:
    """GHS linkage, attrition, power and the run rule."""
    rows: list[dict[str, Any]] = []

    def add(section: str, item_id: str, label: str, kind: str, value: Any = None, text=None):
        rows.append(_item("ghs", section, item_id, label, kind, value, text))

    link = ghs["linkage"]
    for key, label in (
        ("w4_people_15plus", "People aged 15+ in W4"),
        ("found_in_w5", "Found in W5"),
        ("found_with_w5_answers", "Found with W5 answers"),
        ("analysis_sample", "In the analysis sample"),
        ("onset_cases", "Onset of a severe difficulty by W5"),
    ):
        add("linkage", key, label, "count", link[key])
    add("linkage", "linkage_rate", "Linkage rate", "share", link["linkage_rate"])
    for row in ghs["attrition"]:
        key = slug(row["characteristic"].replace("zone=", "zone "))
        for part in ("stayers", "attriters", "standardised_difference"):
            add(
                "attrition",
                f"attrition_{key}_{part}",
                f"{row['characteristic']}: {part}",
                "number",
                row[part],
            )
    for outcome, result in ghs["outcomes"].items():
        power = result["power"]
        for key in ("n", "onset_cases"):
            add("power", f"{outcome}_{key}", f"{outcome}: {key}", "count", power[key])
        for key in ("onset_share", "sd_change", "deff_kish", "icc", "deff", "mde_sd", "mde"):
            add("power", f"{outcome}_{key}", f"{outcome}: {key}", "number", power[key])
        add("power", f"{outcome}_run", f"{outcome}: run under the MDE rule", "flag", power["run"])
        if power["run"]:
            model, check = result["model"], result["r_check"]
            diff = max(abs(model[k] - check[k]) for k in ("estimate", "se", "ci_low", "ci_high"))
            add(
                "r_check",
                f"{outcome}_r_max_abs_diff",
                f"{outcome}: largest difference, R vs Python",
                "number",
                diff,
            )
            add(
                "r_check",
                f"{outcome}_fixest",
                f"{outcome}: R fixest version",
                "text",
                text=str(check.get("fixest")),
            )
    if ghs.get("mode") != "real":
        raise PublishError("ghs_results.json is not a real run")
    return pd.DataFrame(rows, columns=list(disclosure.SUMMARY_COLUMNS))


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def publish_all(
    results: Mapping[str, Any],
    ghs: Mapping[str, Any],
    run_manifest: Mapping[str, Any],
    prereg_text: str,
    out_root: Path = disclosure.AGGREGATES,
    deviations_text: str = "",
) -> dict[str, dict[str, Any]]:
    """Build every table first (so a bad input writes nothing), then publish all four."""
    if run_manifest.get("mode") != "real":
        raise PublishError("the run manifest is not a real run; nothing is published")
    tables = {
        "mpi_estimates": (mpi_estimates(results), MPI, disclosure.publish_estimates),
        "ghs_estimates": (ghs_estimates(ghs), GHS, disclosure.publish_estimates),
        "mpi_summary": (
            mpi_summary(results, run_manifest, prereg_text, deviations_text),
            MPI,
            disclosure.publish_summary,
        ),
        "ghs_summary": (ghs_summary(ghs), GHS, disclosure.publish_summary),
    }
    for frame, dataset, func in tables.values():
        gate = (
            disclosure.gate_estimates
            if func is disclosure.publish_estimates
            else disclosure.gate_summary
        )
        gate(frame, dataset)  # dry run: any GateError stops before a file is written
    entries = {}
    for name, (frame, dataset, func) in tables.items():
        _, entry = func(frame, dataset, FILES[name], out_root)
        entries[name] = entry
    return entries


@c.safe_main
def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Publish the P5 estimates through the gate.")
    parser.add_argument("--results", type=Path, default=RESULTS)
    parser.add_argument("--ghs-results", type=Path, default=GHS_RESULTS)
    parser.add_argument("--manifest", type=Path, default=RUN_MANIFEST)
    parser.add_argument("--out-root", type=Path, default=disclosure.AGGREGATES)
    args = parser.parse_args(argv)
    try:
        entries = publish_all(
            read_json(args.results),
            read_json(args.ghs_results),
            read_json(args.manifest),
            PREREG.read_text(encoding="utf-8"),
            args.out_root,
            DEVIATIONS.read_text(encoding="utf-8") if DEVIATIONS.is_file() else "",
        )
    except (PublishError, disclosure.GateError, KeyError) as exc:
        c.log(f"refused: {type(exc).__name__}: {exc}")
        return 1
    for name, entry in entries.items():
        c.log(f"wrote {FILES[name]}: {entry['rows']} rows, {entry['suppressed_cells']} suppressed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
