"""P5 exploratory E1 (GHS-Panel W4 -> W5): onset of a severe difficulty and the change in
household consumption and in the person's work. ``docs/preregistration.md`` section 8.

A two-period comparison, not an event study: the assumption that the comparison group
shows the change the onset group would have shown is untestable and stated as such.

**Real data are refused until the pre-registration is registered** (the same guard as
:mod:`p5_mpi`); the default mode builds an invented panel (:func:`synthetic_panel`) and runs
the whole E1 pipeline on it. Results stay in ``data/restricted/derived/p5/``.

Map of section 8 to this module:

* domains, onset: :data:`W4_DOMAINS`, :data:`W5_DOMAINS`, :func:`severe_any`;
* sample, linkage, attrition: :func:`build_panel`, :func:`attrition`. The sample rule
  (author's decision of 2026-10-31): all six W4 domains answered and none severe, and a
  known W5 status (a severe answer in some domain, or all six answered);
* outcomes: :func:`any_work` over the same three categories in both waves (author's
  decision of 2026-10-31; :data:`W4_WORK`, :data:`W5_WORK`; reference period: the last 7
  days in both), identified from the files' variable labels (metadata):

  - wage work: W4 ``s3q4`` "worked for someone who is not a member of the HH"; W5
    ``s4aq4`` "any work for someone not an HH member for payment in cash/kind";
  - own farm: W4 ``s3q5`` "worked on a household farm, cared for livestock, or fishing
    activity"; W5 ``s4aq10`` "work on HH farming, livestock, fishing, or forestry
    activities";
  - own business: W4 ``s3q6`` "worked on their own account or in a business";
    W5 ``s4aq6`` "work in a non-farm HH business that [NAME] operates".

  W5's "helping" items (``s4aq8`` non-farm business run by another member, ``s4aq11``
  farming) are left out: W4 has no separate helping item. The wording differences are
  stated with the result. The change in log ``totcons_adj`` (each wave's
  ``totcons_final``) is the other outcome;
* covariates: W4 age band (15-29, 30-44, 45-59, 60+), sex, zone, sector;
* power and the run rule: :func:`icc_anova`, :func:`mde`;
* model: :func:`change_model` (pyfixest ``feols``, longitudinal weight, EA clusters) and
  :func:`r_change_model` (R ``fixest``, ``R/p5_ghs_check.R``).
"""

from __future__ import annotations

import argparse
import json
import math
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats

from curbcut_ingest.restricted import common as c
from curbcut_ingest.restricted.ghs import W4_DIR, W5_DIR, WAVES
from curbcut_ingest.restricted.p5_exposure import OutDirError, restricted_out_dir
from curbcut_ingest.restricted.p5_mpi import (
    OUT_DIR,
    SEED,
    RegistrationError,
    require_registration,
    write_json,
)

MIN_AGE = 15
ALPHA = 0.05
POWER = 0.80
MDE_RULE_SD = 0.5
"""Section 8: E1 runs for an outcome only if its MDE is at most 0.5 SD of the change."""
MIN_ONSET_REPORT = 30
AGE_BANDS = ((15, 29, "15-29"), (30, 44, "30-44"), (45, 59, "45-59"), (60, 200, "60+"))
COVARIATES = ("age_band", "sex", "zone", "sector")
OUTCOMES = {"dlog_consumption": "log household consumption per capita", "dwork": "any work"}

W4_DOMAINS = WAVES["w4"].domains
W5_DOMAINS = WAVES["w5"].domains
W4_WORK = {"wage": "s3q4", "farm_own": "s3q5", "nonfarm_own": "s3q6"}
W5_WORK = {"wage": "s4aq4", "farm_own": "s4aq10", "nonfarm_own": "s4aq6"}
"""Section 8 work outcome: the same three categories in both waves (see the module
docstring for the labels); W5's helping items ``s4aq8`` and ``s4aq11`` are not used."""
YES, NO = 1, 2

W4_FILES = {
    "disability": W4_DIR / "sect4a_harvestw4.dta",
    "roster": W4_DIR / "sect1_harvestw4.dta",
    "cover": W4_DIR / "secta_harvestw4.dta",
    "work": W4_DIR / "sect3_plantingw4.dta",
    "consumption": W4_DIR / "totcons_final.dta",
}
W5_FILES = {
    "disability": W5_DIR / "sect3_plantingw5.dta",
    "roster": W5_DIR / "sect1_plantingw5.dta",
    "cover": W5_DIR / "secta_plantingw5.dta",
    "work": W5_DIR / "sect4a_plantingw5.dta",
    "consumption": c.RESTRICTED / "ghs-w5" / "totcons_final.dta",
}


# --- definitions ---------------------------------------------------------------------


def severe_any(domains: pd.DataFrame) -> pd.Series:
    """1 if any domain is "a lot" or "cannot" (3, 4); 0 if all six are answered and none
    is; missing otherwise (the WG-SS DISABILITY3 rule)."""
    return c.disability3(domains.apply(c.wg_scale))


def any_work(items: pd.DataFrame) -> pd.Series:
    """1 if any item is "yes"; 0 if every item is "no"; missing otherwise."""
    answers = items.apply(c.to_num)
    out = pd.Series(pd.NA, index=items.index, dtype="Int8")
    out[(answers == NO).all(axis=1)] = 0
    out[(answers == YES).any(axis=1)] = 1
    return out


def age_band(age: pd.Series) -> pd.Series:
    age = c.to_num(age)
    out = pd.Series(pd.NA, index=age.index, dtype="string")
    for lo, hi, label in AGE_BANDS:
        out[(age >= lo) & (age <= hi)] = label
    return out


# --- panel, linkage, attrition -------------------------------------------------------


@dataclass(frozen=True)
class Panel:
    frame: pd.DataFrame
    """Analysis sample: one row per linked person 15+ with no severe difficulty in W4 and
    a known W5 status; ``onset``, the two changes, covariates, ``weight``, ``cluster``."""
    linkage: dict[str, Any]
    attrition: list[dict[str, Any]]


def build_panel(w4: pd.DataFrame, w5: pd.DataFrame) -> Panel:
    """Link W4 people 15+ to W5 on (hhid, indiv). Pure; tested on invented rows.

    ``w4``: hhid, indiv, age, sex, zone, sector, cluster, weight_w4, the six domains (1-4),
    work_w4, consumption_w4. ``w5``: hhid, indiv, the six domains, work_w5,
    consumption_w5, weight_long (the W5 longitudinal weight).
    """
    w4 = w4.copy()
    w4["severe_w4"] = severe_any(w4[[f"w4_{d}" for d in c.WG_DOMAINS]])
    base = w4[c.to_num(w4["age"]) >= MIN_AGE].copy()
    w5 = w5.copy()
    w5["severe_w5"] = severe_any(w5[[f"w5_{d}" for d in c.WG_DOMAINS]])
    linked = base.merge(w5, on=["hhid", "indiv"], how="left", validate="one_to_one", indicator=True)
    found = (linked["_merge"] == "both").to_numpy()
    stayed = found & linked["severe_w5"].notna().to_numpy()
    linkage = {
        "w4_people_15plus": c.masked(len(base)),
        "found_in_w5": c.masked(int(found.sum())),
        "linkage_rate": float(found.mean()) if len(base) else float("nan"),
        "found_with_w5_answers": c.masked(int(stayed.sum())),
    }
    table = attrition(linked, stayed)
    sample = linked[stayed & (linked["severe_w4"] == 0).fillna(False).to_numpy()].copy()
    out = pd.DataFrame(index=sample.index)
    out["onset"] = sample["severe_w5"].astype("float64")
    cons4, cons5 = c.to_num(sample["consumption_w4"]), c.to_num(sample["consumption_w5"])
    positive = (cons4 > 0) & (cons5 > 0)
    out["dlog_consumption"] = (
        np.log(cons5.where(positive)) - np.log(cons4.where(positive))
    ).astype("float64")
    out["dwork"] = (c.to_num(sample["work_w5"]) - c.to_num(sample["work_w4"])).astype("float64")
    out["age_band"] = age_band(sample["age"])
    for col in ("sex", "zone", "sector"):
        out[col] = sample[col].astype("string")
    out["weight"] = c.to_num(sample["weight_long"])
    out["cluster"] = sample["cluster"].astype("string")
    keep = out["weight"].notna() & (out["weight"] > 0) & out["cluster"].notna()
    linkage["analysis_sample"] = c.masked(int(keep.sum()))
    linkage["onset_cases"] = c.masked(int(out.loc[keep, "onset"].sum()))
    return Panel(out[keep].reset_index(drop=True), linkage, table)


def attrition(linked: pd.DataFrame, stayed: np.ndarray) -> list[dict[str, Any]]:
    """Stayers vs attriters on W4 characteristics (W4 cross-section weight); no outcome.
    Standardised difference = (stayers - attriters) / pooled SD."""
    w = c.to_num(linked["weight_w4"]).fillna(0).to_numpy()
    rows = []
    features: dict[str, pd.Series] = {
        "age": c.to_num(linked["age"]),
        "female": (linked["sex"].astype("string") == "female").astype("float64"),
        "urban": (linked["sector"].astype("string") == "urban").astype("float64"),
        "severe_w4": c.to_num(linked["severe_w4"]),
    }
    for zone in sorted(linked["zone"].dropna().astype(str).unique()):
        features[f"zone={zone}"] = (linked["zone"].astype("string") == zone).astype("float64")
    for name, values in features.items():
        v = values.to_numpy(dtype="float64")
        ok = ~np.isnan(v) & (w > 0)
        groups = {}
        for label, mask in (("stayers", stayed & ok), ("attriters", ~stayed & ok)):
            if mask.sum() == 0:
                groups[label] = (float("nan"), float("nan"))
                continue
            mean = float(np.average(v[mask], weights=w[mask]))
            var = float(np.average((v[mask] - mean) ** 2, weights=w[mask]))
            groups[label] = (mean, var)
        pooled = math.sqrt((groups["stayers"][1] + groups["attriters"][1]) / 2)
        diff = (
            (groups["stayers"][0] - groups["attriters"][0]) / pooled if pooled > 0 else float("nan")
        )
        rows.append({
            "characteristic": name,
            "stayers": groups["stayers"][0],
            "attriters": groups["attriters"][0],
            "standardised_difference": diff,
        })  # fmt: skip
    return rows


# --- power and the run rule ----------------------------------------------------------


def icc_anova(values: np.ndarray, clusters: np.ndarray) -> float:
    """One-way ANOVA intra-cluster correlation (unequal cluster sizes), floored at 0."""
    frame = pd.DataFrame({"v": values, "g": clusters})
    groups = frame.groupby("g")["v"]
    sizes, means = groups.size().to_numpy(dtype="float64"), groups.mean().to_numpy()
    n, k = float(sizes.sum()), len(sizes)
    if k < 2 or n <= k:
        return 0.0
    grand = float(frame["v"].mean())
    msb = float((sizes * (means - grand) ** 2).sum() / (k - 1))
    msw = float(((frame["v"] - groups.transform("mean")) ** 2).sum() / (n - k))
    n0 = (n - (sizes**2).sum() / n) / (k - 1)
    denom = msb + (n0 - 1) * msw
    return max(0.0, (msb - msw) / denom) if denom > 0 else 0.0


def mde(
    change: np.ndarray,
    onset: np.ndarray,
    weights: np.ndarray,
    clusters: np.ndarray,
    alpha: float = ALPHA,
    power: float = POWER,
) -> dict[str, Any]:
    """Minimum detectable difference in the change between onset and no-onset (section 8).

    MDE = (z_{1-alpha/2} + z_power) * sqrt(deff / (n p (1 - p))) * SD, with SD the pooled
    (unsplit, unweighted) standard deviation of the change, p the (unweighted) onset share,
    deff = Kish's weighting effect n sum(w^2) / (sum w)^2 times the clustering effect
    1 + (m - 1) ICC, m the mean cluster size and ICC that of the change.
    """
    ok = ~np.isnan(change)
    y, d, w, g = change[ok], onset[ok], weights[ok], clusters[ok]
    n = len(y)
    p = float(d.mean()) if n else float("nan")
    sd = float(np.std(y, ddof=1)) if n > 1 else float("nan")
    deff_kish = float(n * (w**2).sum() / w.sum() ** 2) if n else float("nan")
    icc = icc_anova(y, g) if n else 0.0
    m = float(n / len(np.unique(g))) if n else float("nan")
    deff_cluster = 1 + (m - 1) * icc
    deff = deff_kish * deff_cluster
    z = stats.norm.ppf(1 - alpha / 2) + stats.norm.ppf(power)
    mde_sd = float(z * math.sqrt(deff / (n * p * (1 - p)))) if 0 < p < 1 else float("inf")
    return {
        "n": n,
        "onset_cases": int(d.sum()),
        "onset_share": p,
        "sd_change": sd,
        "deff_kish": deff_kish,
        "icc": icc,
        "mean_cluster_size": m,
        "deff_cluster": deff_cluster,
        "deff": deff,
        "mde_sd": mde_sd,
        "mde": mde_sd * sd,
        "run": bool(mde_sd <= MDE_RULE_SD),
    }


# --- the model -----------------------------------------------------------------------


FORMULA = "{y} ~ onset + C(age_band) + C(sex) + C(zone) + C(sector)"


def change_model(frame: pd.DataFrame, outcome: str) -> dict[str, Any]:
    """Change-score WLS (no lagged outcome), longitudinal weight, EA-clustered SEs."""
    from pyfixest.estimation.api import feols

    data = frame[[outcome, "onset", *COVARIATES, "weight", "cluster"]].dropna().copy()
    for col in COVARIATES:
        data[col] = data[col].astype(str)
    data["cluster"] = data["cluster"].astype(str)
    fit = feols(FORMULA.format(y=outcome), data=data, weights="weight", vcov={"CRV1": "cluster"})
    tidy: dict[Any, Any] = fit.tidy().loc["onset"].to_dict()
    return {
        "estimate": float(tidy["Estimate"]),
        "se": float(tidy["Std. Error"]),
        "ci_low": float(tidy["2.5%"]),
        "ci_high": float(tidy["97.5%"]),
        "n": len(data),
    }


R_CHECK = c.ROOT / "packages" / "ingest" / "R" / "p5_ghs_check.R"
R_PREFIX = "p5_ghs_check.R: "


def r_change_model(frame: pd.DataFrame, outcome: str, work: Path) -> dict[str, Any]:
    """The same model in R ``fixest::feols`` (weights, cluster = EA)."""
    from curbcut_ingest import aggregate

    work.mkdir(parents=True, exist_ok=True)
    data = frame[[outcome, "onset", *COVARIATES, "weight", "cluster"]].dropna().copy()
    for col in (*COVARIATES, "cluster"):
        data[col] = data[col].astype(str)
    data = data.rename(columns={outcome: "y"})
    paths = {
        k: work / f"p5_ghs_{outcome}.{k}" for k in ("input.parquet", "output.json", "spec.json")
    }
    data.to_parquet(paths["input.parquet"], index=False)
    spec = {
        "input": paths["input.parquet"].as_posix(),
        "output": paths["output.json"].as_posix(),
        "covariates": list(COVARIATES),
    }
    paths["spec.json"].write_text(json.dumps(spec) + "\n", encoding="utf-8", newline="\n")
    aggregate.run_r([aggregate.rscript(), str(R_CHECK), str(paths["spec.json"])], prefix=R_PREFIX)
    return json.loads(paths["output.json"].read_text(encoding="utf-8"))


def run_e1(panel: Panel, with_r: bool = True, work: Path | None = None) -> dict[str, Any]:
    """Section 8 in order: counts and MDE first; each outcome runs only if its MDE passes."""
    f = panel.frame
    results: dict[str, Any] = {
        "linkage": panel.linkage,
        "attrition": panel.attrition,
        "outcomes": {},
    }
    for outcome in OUTCOMES:
        power = mde(
            f[outcome].to_numpy(dtype="float64"),
            f["onset"].to_numpy(dtype="float64"),
            f["weight"].to_numpy(dtype="float64"),
            f["cluster"].astype(str).to_numpy(),
        )
        entry: dict[str, Any] = {"power": power}
        if power["onset_cases"] < MIN_ONSET_REPORT:
            power["onset_cases"] = c.masked(power["onset_cases"])
        if power["run"]:
            entry["model"] = change_model(f, outcome)
            if with_r:
                entry["r_check"] = r_change_model(f, outcome, work or OUT_DIR / "work")
        else:
            entry["not_run"] = f"MDE {power['mde_sd']:.2f} SD exceeds the {MDE_RULE_SD} SD rule"
        results["outcomes"][outcome] = entry
    return results


# --- synthetic panel -----------------------------------------------------------------


def synthetic_panel(
    n_households: int = 1500,
    members: int = 4,
    seed: int = SEED,
    onset_rate: float = 0.08,
    consumption_effect: float = -0.15,
    work_effect: float = -0.10,
    attrition_rate: float = 0.15,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Invented W4 and W5 person files with the :func:`build_panel` schema."""
    rng = np.random.default_rng(seed)
    n_clusters = max(2, n_households // 10)
    zones = ["North Central", "North East", "North West", "South East", "South South", "South West"]
    hh = pd.DataFrame({"hhid": np.arange(n_households) + 1})
    hh["cluster"] = (hh["hhid"] - 1) % n_clusters
    hh["zone"] = [zones[k % 6] for k in hh["cluster"]]
    urban_cluster = rng.random(n_clusters) < 0.35
    hh["sector"] = np.where(urban_cluster[hh["cluster"].to_numpy()], "urban", "rural")
    hh["weight_w4"] = rng.uniform(500, 3000, n_households)
    cluster_shock = rng.normal(0, 0.15, n_clusters)
    hh["consumption_w4"] = np.exp(rng.normal(12, 0.6, n_households))
    people = hh.loc[hh.index.repeat(members)].reset_index(drop=True)
    people["indiv"] = people.groupby("hhid").cumcount() + 1
    n = len(people)
    people["age"] = rng.integers(5, 85, n)
    people["sex"] = np.where(rng.random(n) < 0.5, "female", "male")
    for d in c.WG_DOMAINS:
        people[f"w4_{d}"] = rng.choice([1, 2, 3], n, p=[0.9, 0.085, 0.015])
    people.loc[rng.random(n) < 0.01, "w4_seeing"] = np.nan
    people["work_w4"] = (rng.random(n) < 0.6).astype("float64")
    stays = rng.random(n) >= attrition_rate
    w5 = people.loc[stays, ["hhid", "indiv"]].copy()
    m = len(w5)
    onset = rng.random(m) < onset_rate
    for d in c.WG_DOMAINS:
        w5[f"w5_{d}"] = rng.choice([1, 2], m, p=[0.92, 0.08])
    w5.loc[onset, "w5_walking"] = 3
    w5["onset_true"] = onset
    src = people.loc[stays]
    growth = 0.10 + cluster_shock[src["cluster"].to_numpy()] + rng.normal(0, 0.3, m)
    # Consumption is a household variable: the effect enters through the person's change.
    w5["consumption_w5"] = src["consumption_w4"].to_numpy() * np.exp(
        growth + consumption_effect * onset
    )
    p_work = np.clip(0.6 + work_effect * onset, 0, 1)
    w5["work_w5"] = (rng.random(m) < p_work).astype("float64")
    w5["weight_long"] = src["weight_w4"].to_numpy() * rng.uniform(0.9, 1.3, m)
    w4 = people.copy()
    return w4, w5.drop(columns="onset_true")


# --- real-data loading (guarded) -----------------------------------------------------


def load_real() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Read the named columns only and assemble the :func:`build_panel` inputs. Guarded
    here too, not only in :func:`main`: refused (:class:`RegistrationError`) until the
    pre-registration is registered."""
    require_registration()
    from curbcut_ingest.restricted.common import read_dta

    def person(
        files: Mapping[str, Path], domains: Mapping[str, str], work: Mapping[str, str], prefix: str
    ) -> pd.DataFrame:
        dis, _ = read_dta(files["disability"], ["hhid", "indiv", *domains.values()])
        wk, _ = read_dta(files["work"], ["hhid", "indiv", *work.values()])
        cons, _ = read_dta(files["consumption"], ["hhid", "totcons_adj"])
        out = dis.rename(columns={v: f"{prefix}_{d}" for d, v in domains.items()})
        out = out.merge(
            wk.assign(**{f"work_{prefix}": any_work(wk[list(work.values())])})[
                ["hhid", "indiv", f"work_{prefix}"]
            ],
            on=["hhid", "indiv"],
            how="left",
            validate="one_to_one",
        )
        return out.merge(
            cons.rename(columns={"totcons_adj": f"consumption_{prefix}"}),
            on="hhid",
            how="left",
            validate="many_to_one",
        )

    w4 = person(W4_FILES, W4_DOMAINS, W4_WORK, "w4")
    roster4, _ = read_dta(W4_FILES["roster"], ["hhid", "indiv", "s1q2", "s1q4"])
    cover4, meta4 = read_dta(W4_FILES["cover"], ["hhid", "zone", "sector", "cluster", "wt_wave4"])
    zone_labels = c.value_labels(meta4, "zone")
    w4 = w4.merge(roster4, on=["hhid", "indiv"], how="inner", validate="one_to_one")
    w4 = w4.merge(cover4, on="hhid", how="inner", validate="many_to_one")
    w4["age"] = c.to_num(w4["s1q4"])
    w4["sex"] = c.recode(w4["s1q2"], c.SEX)
    w4["sector"] = c.recode(w4["sector"], c.SECTOR)
    w4["zone"] = c.to_num(w4["zone"]).map(
        lambda v: zone_labels.get(int(v)) if pd.notna(v) else pd.NA
    )
    w4["weight_w4"] = c.to_num(w4["wt_wave4"])

    w5 = person(W5_FILES, W5_DOMAINS, W5_WORK, "w5")
    roster5, _ = read_dta(W5_FILES["roster"], ["hhid", "indiv"])
    cover5, _ = read_dta(W5_FILES["cover"], ["hhid", "wt_wave5"])
    w5 = roster5.merge(w5, on=["hhid", "indiv"], how="left", validate="one_to_one")
    w5 = w5.merge(cover5, on="hhid", how="left", validate="many_to_one")
    w5["weight_long"] = c.to_num(w5["wt_wave5"])
    return w4, w5


@c.safe_main
def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="P5 E1: GHS W4 -> W5 onset comparison (synthetic by default)."
    )
    parser.add_argument(
        "--real", action="store_true", help="real files (refused until OSF registration)"
    )
    parser.add_argument("--no-r", action="store_true", help="skip the R cross-check")
    parser.add_argument("--out-dir", type=Path, default=None)
    args = parser.parse_args(argv)
    if args.out_dir is not None:
        try:
            args.out_dir = restricted_out_dir(args.out_dir)
        except OutDirError as exc:
            c.log(f"refused: {exc}")
            return 2
    start = time.perf_counter()
    if args.real:
        try:
            url = require_registration()
        except RegistrationError as exc:
            c.log(f"refused: {exc}")  # the message names the rule, never data
            return 1
        c.log(f"P5 GHS: real data (registered: {url})")
        w4, w5 = load_real()
        out_dir = args.out_dir or OUT_DIR
    else:
        c.log("P5 GHS: SYNTHETIC data (invented; no real file is read)")
        w4, w5 = synthetic_panel()
        out_dir = args.out_dir or OUT_DIR / "synthetic"
    results = run_e1(build_panel(w4, w5), with_r=not args.no_r, work=out_dir / "work")
    results["mode"] = "real" if args.real else "synthetic"
    results["elapsed_seconds"] = round(time.perf_counter() - start, 1)
    write_json(results, out_dir / "ghs_results.json")
    for outcome, entry in results["outcomes"].items():
        power = entry["power"]
        state = "run" if power["run"] else "not run"
        c.log(f"  {outcome}: MDE {power['mde_sd']:.2f} SD -> {state}")
    c.log(f"wrote ghs_results.json ({results['elapsed_seconds']} s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
