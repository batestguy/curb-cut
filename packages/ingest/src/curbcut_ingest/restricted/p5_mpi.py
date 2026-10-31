"""P5 primary analysis (MPI 2021): adjusted association between a household member's
severe functional difficulty and multidimensional poverty, as pre-registered.

Implements ``docs/preregistration.md`` sections 3-7. Every number, rule and seed below is
taken from that document; the section is named next to each. The result is an
**adjusted association**, never "the effect of disability" (section 7). DoubleML's names
("treatment", "ATE", "IRM") are only its API.

**Real data are refused until the pre-registration is registered** (:func:`require_registration`):
section 11 must hold an OSF URL. The default mode is synthetic: :func:`synthetic_households`
makes a household file with the same schema and a known population-weighted difference,
and the whole pipeline runs on it. Nothing here writes to ``data/public/``: results and the
run manifest go to ``data/restricted/derived/p5/`` (git-ignored); a later step passes what
is published through the disclosure gate (section 9).

Map of the pre-registration to this module:

* 3.1 sample, weights, clusters: :func:`analysis_frame`, :func:`normalised_weights`,
  :func:`kish`;
* 3.3 outcomes (incl. S1, S4 and the outcome robustness): :func:`analysis_frame`;
* 3.4 confounders: :data:`COVARIATE_SETS`, :func:`design`;
* 5.1 estimator: :func:`make_learner`, :class:`NaturalCubicSpline`, :func:`fit_irm`;
  learner selection: :func:`select_learners`; overlap: :func:`raw_propensity`,
  :func:`overlap`;
* 5.3 sensitivity: :func:`sensitivity`, :func:`benchmark`, :func:`evalue`,
  :func:`risk_ratio`, :func:`mu0`; sensemakr and the survey LPM (5.2): ``R/p5_benchmark.R``
  via :func:`r_benchmark`;
* 5.4 refutations: :func:`placebo`, :func:`random_common_cause`, :func:`leave_one_zone_out`;
  robustness: :func:`robustness`;
* 5.5 secondaries and Holm: :func:`secondaries`, :func:`holm`; X1: :func:`subgroups`;
* 5.6 Table 7 check: :func:`table7_check`;
* 4 wording rule: :func:`wording`;
* 9 manifest: :func:`manifest` (with :data:`NOTES`, the stated deviations and caveats).

Robustness of the run itself: every step after the primary estimate is wrapped
(:func:`attempt`), so a failing step records its error type and message template (numbers
replaced, no data values) instead of ending the run, and ``results.json`` and the manifest
are rewritten after every step. Warnings raised while fitting are counted by category and
message template (:data:`WARNINGS`), not suppressed.
"""

from __future__ import annotations

import argparse
import copy
import datetime as dt
import hashlib
import json
import math
import platform
import re
import subprocess
import time
import warnings
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass, field, replace
from importlib import metadata
from pathlib import Path
from typing import Any, ClassVar

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import (
    HistGradientBoostingClassifier,
    HistGradientBoostingRegressor,
    RandomForestClassifier,
    RandomForestRegressor,
)
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from curbcut_ingest.restricted import common as c
from curbcut_ingest.restricted.mpi2021_poverty import DIMENSIONS, WEIGHTS
from curbcut_ingest.restricted.mpi2021_poverty import NAME as HOUSEHOLD_NAME
from curbcut_ingest.restricted.p5_exposure import NAME as EXPOSURE_NAME
from curbcut_ingest.restricted.p5_exposure import OutDirError, restricted_out_dir

# --- fixed by the pre-registration ---------------------------------------------------

SEED = 20261030
"""Section 5.1: the seed for the folds and every learner."""
PREREG = c.ROOT / "docs" / "preregistration.md"
OUT_DIR = c.DERIVED / "p5"
OSF_URL = re.compile(r"https://osf\.io/[A-Za-z0-9][A-Za-z0-9_./-]*")

PS_CLIP = 0.01
"""5.1: propensity scores clipped at 0.01 and 0.99 (DoubleML clips; nothing is dropped).
The overlap population (5.1, author's decision of 2026-10-31) is the households whose mean
cross-fitted propensity lies in [PS_CLIP, 1 - PS_CLIP]; its estimate is always reported."""
OVERLAP_QUANTILES = (0.01, 0.05, 0.25, 0.5, 0.75, 0.95, 0.99)
"""5.1: the propensity quantiles reported for each exposure group."""
SMALLEST_DIFFERENCE = 0.02
"""Section 4: 2 percentage points."""
ALPHA = 0.05
TABLE7 = {"exposed": 71.4, "unexposed": 61.8, "gap": 9.6}
TABLE7_TOLERANCE = 2.0
"""5.6: NBS Table 7 (D61), percentage points, +/- 2.0 each."""
PREFERENCE = ("logistic", "forest", "boosting")
"""5.1: the order in which candidates within one SE of the best are preferred."""
EXPOSURES = {
    "primary": "exposed_primary",
    "s2": "exposed_s2",
    "s3": "exposed_s3",
    "s5": "exposed_s5",
    "s6": "exposed_s6",
}
DIMENSION_OUTCOMES = {f"dim_{d}": d for d in DIMENSIONS}

CATEGORICAL = ("state", "district", "head_sex", "head_education")
NATIVE_CATEGORICAL = ("state", "district", "head_education")
"""5.1: the gradient-boosting learner treats these as native categorical features."""
COUNTS = ("n_0_4", "n_5", "n_6_14", "n_15_17", "n_18_59", "n_60_69", "n_70plus")
"""3.4: household age structure (MPI eligibility ages, and the very old)."""
FULL = ("state", "district", "sector", *COUNTS, "head_sex", "head_age", "head_education")
COVARIATE_SETS: dict[str, tuple[str, ...]] = {
    "primary": FULL,
    "no_head_education": tuple(v for v in FULL if v != "head_education"),
    "place_head_sex_age": ("state", "district", "sector", "head_sex", "head_age"),
    "state_only_place": tuple(v for v in FULL if v != "district"),
}
"""3.4 and 5.4: the primary adjustment set and the robustness sets. S3 uses
``no_head_education``."""
BENCHMARKS = {
    "head_education": ["head_education"],
    "place": ["state", "district"],
    "sector": ["sector"],
}
"""5.3: observed covariates the omitted-variable bounds are benchmarked on. "place" drops
both state and senatorial district (district is state x senatorial district, so dropping
state alone would leave place in the model; author's decision of 2026-10-31)."""
NOTES = (
    "DoubleML's normalize_ipw normalises the inverse-probability weights with unweighted "
    "means, even when survey weights are passed. The score is doubly robust, so this is "
    "not a bias; the survey weights still set the target population.",
    "The omitted-variable bounds are benchmarked with this module's benchmark(), not "
    "DoubleML's sensitivity_benchmark: the short model's learners are rebuilt for the "
    "shorter column layout, because the learners address columns by position (a stated "
    "deviation, pre-registration 5.3).",
    "trimming_threshold=0.01 is used as the pre-registration names it; on doubleml 0.11.4 "
    "it is a deprecated alias of the propensity clipping threshold (removed in 0.12).",
)
"""Section 9: stated deviations and caveats, written into every manifest."""


@dataclass(frozen=True)
class Settings:
    """Run sizes. :data:`PREREGISTERED` is what the pre-registration fixes; tests and
    ``--quick`` synthetic runs shrink them. Real data always use :data:`PREREGISTERED`."""

    n_folds: int = 5
    n_rep: int = 5
    refutation_n_rep: int = 1
    n_placebo: int = 100
    n_fold_seeds: int = 5
    forest_trees: int = 500
    boosting_iter: int = 300
    families: tuple[str, ...] = PREFERENCE


PREREGISTERED = Settings()
QUICK = Settings(n_rep=2, n_placebo=10, n_fold_seeds=3, forest_trees=50, boosting_iter=50)


NUMBER = re.compile(r"[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?")


def message_template(message: str) -> str:
    """A warning or error message with every number replaced by "#" (no data values),
    whitespace collapsed, at most 200 characters."""
    return NUMBER.sub("#", " ".join(str(message).split()))[:200]


class WarningTally:
    """Warnings raised while fitting, counted by category and message template."""

    def __init__(self) -> None:
        self.counts: Counter[str] = Counter()

    def add(self, caught: Sequence[warnings.WarningMessage]) -> None:
        for w in caught:
            self.counts[f"{w.category.__name__}: {message_template(str(w.message))}"] += 1

    def as_dict(self) -> dict[str, int]:
        return dict(sorted(self.counts.items()))


WARNINGS = WarningTally()
"""Every warning raised by :func:`fit_irm` and :func:`benchmark` in this run."""


def error_entry(exc: BaseException) -> dict[str, str]:
    """A failed step's record: the exception type and its message template."""
    return {"error": type(exc).__name__, "message": message_template(str(exc))}


def failed_steps(results: Any, path: str = "") -> list[str]:
    """The dotted path of every step in ``results`` that recorded :func:`error_entry`."""
    if isinstance(results, Mapping):
        if "error" in results and "message" in results:
            return [path]
        return [
            name
            for key, value in results.items()
            for name in failed_steps(value, f"{path}.{key}" if path else str(key))
        ]
    if isinstance(results, list):
        return [
            name for i, value in enumerate(results) for name in failed_steps(value, f"{path}[{i}]")
        ]
    return []


def attempt(func: Callable[[], Any]) -> Any:
    """``func()``, or :func:`error_entry` if it raises: a failing step does not end the run."""
    try:
        return func()
    except Exception as exc:
        return error_entry(exc)


class RegistrationError(RuntimeError):
    """Raised when real data are requested before the OSF registration exists."""


def registration_url(text: str) -> str | None:
    """The OSF URL in section 11 ("Registration record") of the pre-registration, if any."""
    match = re.search(r"^## 11\.[^\n]*\n(.*?)(?=^## |\Z)", text, flags=re.M | re.S)
    if match is None:
        return None
    found = OSF_URL.search(match.group(1))
    return found.group(0) if found else None


def require_registration(path: Path = PREREG) -> str:
    """Refuse to go on unless section 11 of the pre-registration holds an OSF URL (rule:
    no poverty-by-disability figure before the OSF timestamp)."""
    url = registration_url(path.read_text(encoding="utf-8")) if path.is_file() else None
    if url is None:
        raise RegistrationError(
            "real-data analysis refused: docs/preregistration.md section 11 has no OSF URL "
            "(the pre-registration is not registered yet)"
        )
    return url


# --- analysis frame (3.1, 3.3, 3.4) --------------------------------------------------


def dimension_scores(households: pd.DataFrame) -> pd.DataFrame:
    """S4: each dimension's weighted deprivation score (sum of indicator weight x
    deprivation; the four add up to the overall score). Missing if any indicator is."""
    out = pd.DataFrame(index=households.index)
    for name, dimension in DIMENSION_OUTCOMES.items():
        parts = [
            households[f"d_{k}"].astype("Float64") * float(WEIGHTS[k])
            for k in DIMENSIONS[dimension]
        ]
        out[name] = sum(parts[1:], parts[0])
    return out


def analysis_frame(
    households: pd.DataFrame, exposure: pd.DataFrame
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Join the household rebuild (D64) and the exposure flags into the analysis frame.

    Sample (3.1): completed interview (``a9a`` = 1), positive ``pop_wgt``, at least one
    member 5+ in Section D. Rows with a missing outcome or exposure stay in the frame (each
    analysis drops them for itself) and are counted in the returned summary.
    """
    frame = households.merge(exposure, on="hh_id", how="inner", validate="one_to_one")
    sample = (frame["a9a"] == 1) & (frame["pop_wgt"] > 0) & frame["in_sample"].astype(bool)
    frame = frame[sample.fillna(False).astype(bool)].copy()
    out = pd.DataFrame(index=frame.index)
    out["hh_id"] = frame["hh_id"]
    out["cluster"] = frame["psu"].astype("string")
    out["state"] = frame["state"].astype("string")
    out["district"] = (
        frame["state"].astype("string") + "-" + frame["senatorial_district"].astype("string")
    )
    out["zone"] = frame["zone"].astype("string")
    out["sector"] = frame["sector"].astype("string")
    for col in COUNTS:
        out[col] = frame[col].astype("float64")
    out["head_sex"] = frame["head_sex"].astype("string")
    out["head_age"] = frame["head_age"].astype("Float64")
    out["head_education"] = frame["head_education"].astype("string")
    out["pop_wgt"] = frame["pop_wgt"].astype("float64")
    out["poor"] = frame["poor"].astype("Float64")
    out["score"] = frame["score"].astype("Float64")
    out["poor_fuel_alt"] = frame["poor_fuel_alt"].astype("Float64")
    out["poor_shock_dk0"] = frame["poor_shock_dk0"].astype("Float64")
    out = out.join(dimension_scores(frame))
    for name, column in EXPOSURES.items():
        out[column] = frame[column].astype("Float64")
        del name
    summary = {
        "households_in_sample": len(out),
        "missing_poor": _missing_summary(out, out["poor"].isna()),
        "missing_exposure_primary": _missing_summary(out, out["exposed_primary"].isna()),
    }
    return out.reset_index(drop=True), summary


def _missing_summary(frame: pd.DataFrame, missing: pd.Series) -> dict[str, Any]:
    w = frame["pop_wgt"]
    return {
        "households": c.masked(int(missing.sum())),
        "weighted_share_people": float(w[missing].sum() / w.sum()),
    }


def normalised_weights(weights: pd.Series | np.ndarray) -> np.ndarray:
    """3.1/5.1: population weights normalised to mean 1 (DoubleML's ``weights``)."""
    w = np.asarray(weights, dtype="float64")
    return w / w.mean()


def kish(weights: pd.Series | np.ndarray) -> dict[str, float]:
    """3.1: Kish effective sample size (sum w)^2 / sum w^2 and the largest weight's share."""
    w = np.asarray(weights, dtype="float64")
    return {
        "n": int(w.size),
        "kish_effective_n": float(w.sum() ** 2 / (w**2).sum()),
        "max_weight_share": float(w.max() / w.sum()),
    }


# --- design matrix and learners (3.4, 5.1) -------------------------------------------


@dataclass(frozen=True)
class Layout:
    """Column roles of the numeric design matrix (the order DoubleML passes to learners)."""

    columns: tuple[str, ...]
    categorical: tuple[str, ...]
    age: tuple[str, ...]
    numeric: tuple[str, ...]

    def index(self, names: Sequence[str]) -> list[int]:
        return [self.columns.index(n) for n in names if n in self.columns]


MISSING_CODE = "missing"


def design(
    frame: pd.DataFrame, covariates: Sequence[str], extra_numeric: Sequence[str] = ()
) -> tuple[pd.DataFrame, Layout]:
    """Numeric design matrix: categoricals as integer codes with an explicit "missing"
    category (section 6); head's age with missing values set to the median and a
    missing indicator; counts and sector as numbers; ``extra_numeric`` appended (the
    random common cause)."""
    x = pd.DataFrame(index=frame.index)
    categorical, age, numeric = [], [], []
    for name in covariates:
        if name in CATEGORICAL:
            values = frame[name].astype("string").fillna(MISSING_CODE)
            x[name] = pd.Categorical(values, categories=sorted(set(values))).codes.astype("float64")
            categorical.append(name)
        elif name == "head_age":
            value = pd.to_numeric(frame[name], errors="coerce").astype("float64")
            missing = value.isna()
            x[name] = value.fillna(value.median() if value.notna().any() else 0.0)
            age.append(name)
            if missing.any():
                x["head_age_missing"] = missing.astype("float64")
                numeric.append("head_age_missing")
        elif name == "sector":
            x[name] = (frame[name].astype("string") == "urban").astype("float64")
            numeric.append(name)
        else:
            x[name] = pd.to_numeric(frame[name], errors="coerce").astype("float64")
            numeric.append(name)
    for name in extra_numeric:
        x[name] = frame[name].astype("float64")
        numeric.append(name)
    layout = Layout(tuple(x.columns), tuple(categorical), tuple(age), tuple(numeric))
    return x, layout


class NaturalCubicSpline(BaseEstimator, TransformerMixin):
    """Natural (restricted) cubic spline basis of one column, knots at quantiles.

    Harrell's parametrisation: x plus k-2 terms, linear beyond the boundary knots. With 5
    knots the quantiles are Harrell's defaults (0.05, 0.275, 0.5, 0.725, 0.95). Knots that
    coincide (few distinct values) are merged; with fewer than 3 distinct knots only x is
    returned.
    """

    QUANTILES: ClassVar[dict[int, tuple[float, ...]]] = {
        3: (0.1, 0.5, 0.9),
        4: (0.05, 0.35, 0.65, 0.95),
        5: (0.05, 0.275, 0.5, 0.725, 0.95),
    }

    def __init__(self, n_knots: int = 5) -> None:
        self.n_knots = n_knots

    def fit(self, X: Any, y: Any = None) -> NaturalCubicSpline:
        x = np.asarray(X, dtype="float64")[:, 0]
        self.knots_ = np.unique(np.quantile(x, self.QUANTILES[self.n_knots]))
        return self

    def transform(self, X: Any) -> np.ndarray:
        x = np.asarray(X, dtype="float64")[:, 0]
        t = self.knots_
        k = len(t)
        if k < 3:
            return x[:, None]
        scale = (t[-1] - t[0]) ** 2

        def cube(v: np.ndarray) -> np.ndarray:
            return np.clip(v, 0, None) ** 3

        cols = [x]
        for j in range(k - 2):
            term = (
                cube(x - t[j])
                - cube(x - t[-2]) * (t[-1] - t[j]) / (t[-1] - t[-2])
                + cube(x - t[-1]) * (t[-2] - t[j]) / (t[-1] - t[-2])
            )
            cols.append(term / scale)
        return np.column_stack(cols)


def make_learner(
    family: str, kind: str, layout: Layout, settings: Settings = PREREGISTERED, seed: int = SEED
) -> Any:
    """A learner with the pre-registered hyper-parameters (5.1); ``kind`` is
    ``"classifier"`` or ``"regressor"`` (the latter for S1 and S4's continuous scores)."""
    cat = layout.index(layout.categorical)
    age = layout.index(layout.age)
    num = layout.index(layout.numeric)
    onehot = OneHotEncoder(handle_unknown="ignore", sparse_output=False)
    classifier = kind == "classifier"
    if family == "logistic":
        prep = ColumnTransformer(
            [
                ("cat", onehot, cat),
                (
                    "age",
                    Pipeline([("spline", NaturalCubicSpline(5)), ("scale", StandardScaler())]),
                    age,
                ),
                ("num", StandardScaler(), num),
            ]
        )
        model = LogisticRegression(C=1.0, max_iter=5000) if classifier else Ridge(alpha=1.0)
        return Pipeline([("prep", prep), ("model", model)])
    if family == "forest":
        prep = ColumnTransformer([("cat", onehot, cat)], remainder="passthrough")
        forest_args = {
            "n_estimators": settings.forest_trees,
            "min_samples_leaf": 20,
            "max_features": "sqrt",
            "random_state": seed,
            "n_jobs": -1,
        }
        model = (
            RandomForestClassifier(**forest_args)
            if classifier
            else RandomForestRegressor(**forest_args)
        )
        return Pipeline([("prep", prep), ("model", model)])
    if family == "boosting":
        native = layout.index([n for n in NATIVE_CATEGORICAL if n in layout.categorical])
        boost_args = {
            "max_iter": settings.boosting_iter,
            "learning_rate": 0.05,
            "max_leaf_nodes": 31,
            "min_samples_leaf": 50,
            "early_stopping": False,
            "categorical_features": native or None,
            "random_state": seed,
        }
        return (
            HistGradientBoostingClassifier(**boost_args)
            if classifier
            else HistGradientBoostingRegressor(**boost_args)
        )
    raise ValueError(f"unknown learner family: {family}")


def is_binary(y: pd.Series | np.ndarray) -> bool:
    values = np.unique(np.asarray(y, dtype="float64"))
    return bool(np.isin(values, [0.0, 1.0]).all())


# --- the estimator (5.1) -------------------------------------------------------------


@dataclass
class Prepared:
    """One analysis's rows, design and DoubleML data (outcome and exposure non-missing)."""

    frame: pd.DataFrame
    x: pd.DataFrame
    layout: Layout
    y: np.ndarray
    d: np.ndarray
    cluster: np.ndarray
    weights: np.ndarray
    binary: bool
    covariates: tuple[str, ...]
    extra_numeric: tuple[str, ...] = ()
    dropped: dict[str, Any] = field(default_factory=dict)


def prepare(
    frame: pd.DataFrame,
    outcome: str,
    exposure: str,
    covariates: Sequence[str],
    extra_numeric: Sequence[str] = (),
) -> Prepared:
    keep = frame[outcome].notna() & frame[exposure].notna()
    sub = frame[keep].reset_index(drop=True)
    x, layout = design(sub, covariates, extra_numeric)
    y = sub[outcome].astype("float64").to_numpy()
    return Prepared(
        frame=sub,
        x=x,
        layout=layout,
        y=y,
        d=sub[exposure].astype("float64").to_numpy(),
        cluster=pd.Categorical(sub["cluster"].astype("string")).codes.astype("int64"),
        weights=normalised_weights(sub["pop_wgt"]),
        binary=is_binary(y),
        covariates=tuple(covariates),
        extra_numeric=tuple(extra_numeric),
        dropped={"rows_dropped_missing": c.masked(int((~keep).sum()))},
    )


def dml_data(p: Prepared) -> Any:
    from doubleml import DoubleMLData

    data = p.x.copy()
    data["_y"] = p.y
    data["_d"] = p.d
    data["_cluster"] = p.cluster
    return DoubleMLData(
        data, y_col="_y", d_cols="_d", x_cols=list(p.layout.columns), cluster_cols="_cluster"
    )


def new_irm(
    p: Prepared,
    learners: tuple[str, str],
    n_rep: int,
    seed: int,
    settings: Settings,
    weighted: bool = True,
) -> Any:
    """A DoubleMLIRM exactly as 5.1 specifies; the folds are drawn here, by cluster, from
    ``seed`` (DoubleML draws them with NumPy's global generator)."""
    from doubleml import DoubleMLIRM

    kind_g = "classifier" if p.binary else "regressor"
    ml_g = make_learner(learners[0], kind_g, p.layout, settings, seed)
    ml_m = make_learner(learners[1], "classifier", p.layout, settings, seed)
    np.random.seed(seed)
    with warnings.catch_warnings(record=True) as caught:
        # trimming_threshold is DoubleML's deprecated alias of the same clipping; it is
        # the parameter the pre-registration names. Any warning is counted, not hidden.
        warnings.simplefilter("always")
        irm = DoubleMLIRM(
            dml_data(p),
            ml_g,
            ml_m,
            n_folds=settings.n_folds,
            n_rep=n_rep,
            score="ATE",
            weights=p.weights if weighted else None,
            normalize_ipw=True,
            trimming_threshold=PS_CLIP,
        )
    WARNINGS.add(caught)
    return irm


@dataclass
class Estimate:
    coef: float
    se: float
    ci_low: float
    ci_high: float
    pval: float
    n: int
    n_exposed: str
    all_coef: list[float]
    mu0: float
    learners: tuple[str, str]
    n_rep: int

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def fit_irm(
    p: Prepared,
    learners: tuple[str, str],
    settings: Settings,
    n_rep: int | None = None,
    seed: int = SEED,
    weighted: bool = True,
) -> tuple[Estimate, Any]:
    """Fit DoubleMLIRM (5.1) and return the estimate and the fitted object."""
    n_rep = settings.n_rep if n_rep is None else n_rep
    dml = new_irm(p, learners, n_rep, seed, settings, weighted)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        dml.fit(store_predictions=True)
    WARNINGS.add(caught)
    ci = dml.confint(level=1 - ALPHA)
    est = Estimate(
        coef=float(dml.coef[0]),
        se=float(dml.se[0]),
        ci_low=float(ci.iloc[0, 0]),
        ci_high=float(ci.iloc[0, 1]),
        pval=float(dml.pval[0]),
        n=len(p.y),
        n_exposed=c.masked(int(p.d.sum())),
        all_coef=[float(v) for v in np.asarray(dml.all_coef).ravel()],
        mu0=mu0(dml, p, weighted),
        learners=learners,
        n_rep=n_rep,
    )
    return est, dml


def mu0(dml: Any, p: Prepared, weighted: bool = True) -> float:
    """5.3: the weighted doubly robust estimate of the outcome share without exposure,
    with normalised inverse-probability weights; the median over repetitions."""
    w = p.weights if weighted else np.ones_like(p.y)
    g0_all = np.asarray(dml.predictions["ml_g0"])[:, :, 0]
    m_all = np.clip(np.asarray(dml.predictions["ml_m"])[:, :, 0], PS_CLIP, 1 - PS_CLIP)
    values = []
    for r in range(g0_all.shape[1]):
        g0, m = g0_all[:, r], m_all[:, r]
        h = (1 - p.d) / (1 - m)
        values.append(float((w * g0).sum() / w.sum() + (w * h * (p.y - g0)).sum() / (w * h).sum()))
    return float(np.median(values))


# --- learner selection (5.1) ---------------------------------------------------------


def first_rep_folds(
    p: Prepared, settings: Settings, seed: int = SEED
) -> list[tuple[np.ndarray, np.ndarray]]:
    """The cluster-based split of the first repetition, exactly as the primary fit draws it."""
    dml = new_irm(p, (settings.families[0], settings.families[0]), settings.n_rep, seed, settings)
    return [(np.asarray(tr), np.asarray(te)) for tr, te in dml.smpls[0]]


def _loss(y: np.ndarray, pred: np.ndarray, binary: bool) -> np.ndarray:
    if binary:
        q = np.clip(pred, 1e-15, 1 - 1e-15)
        return -(y * np.log(q) + (1 - y) * np.log(1 - q))
    return (y - pred) ** 2


def _predict(model: Any, x: pd.DataFrame, binary: bool) -> np.ndarray:
    return model.predict_proba(x.to_numpy())[:, 1] if binary else model.predict(x.to_numpy())


def fold_losses(
    p: Prepared,
    family: str,
    target: str,
    folds: Sequence[tuple[np.ndarray, np.ndarray]],
    settings: Settings,
) -> list[float]:
    """Unweighted out-of-fold loss per fold (log loss for binary targets, squared error
    otherwise). ``target`` is ``"outcome"`` (each arm's model predicts its own arm, as
    DoubleML's g0/g1) or ``"propensity"``."""
    out = []
    for train, test in folds:
        if target == "propensity":
            model = make_learner(family, "classifier", p.layout, settings)
            model.fit(p.x.iloc[train].to_numpy(), p.d[train])
            losses = _loss(p.d[test], _predict(model, p.x.iloc[test], True), True)
        else:
            kind = "classifier" if p.binary else "regressor"
            losses = np.empty(len(test))
            for arm in (0.0, 1.0):
                tr = train[p.d[train] == arm]
                te_mask = p.d[test] == arm
                if not te_mask.any():
                    continue
                model = make_learner(family, kind, p.layout, settings)
                model.fit(p.x.iloc[tr].to_numpy(), p.y[tr])
                te = test[te_mask]
                losses[te_mask] = _loss(p.y[te], _predict(model, p.x.iloc[te], p.binary), p.binary)
        out.append(float(losses.mean()))
    return out


def one_se_choice(losses: Mapping[str, Sequence[float]]) -> tuple[str, dict[str, Any]]:
    """5.1: the lowest mean loss wins; any candidate within one standard error of the
    lowest (the SE of the best candidate's mean across folds) is preferred in the order
    logistic, random forest, gradient boosting."""
    summary = {}
    for family, values in losses.items():
        v = np.asarray(values, dtype="float64")
        summary[family] = {
            "mean": float(v.mean()),
            "se": float(v.std(ddof=1) / math.sqrt(len(v))),
            "folds": [float(x) for x in v],
        }
    best = min(summary, key=lambda f: summary[f]["mean"])
    threshold = summary[best]["mean"] + summary[best]["se"]
    eligible = [f for f in PREFERENCE if f in summary and summary[f]["mean"] <= threshold]
    chosen = eligible[0]
    return chosen, {"candidates": summary, "lowest": best, "threshold": threshold, "chosen": chosen}


def select_learners(
    p: Prepared, settings: Settings, seed: int = SEED
) -> tuple[tuple[str, str], dict[str, Any]]:
    """Choose the outcome and propensity learners before any exposure difference is
    computed (5.1). Returns (outcome family, propensity family) and the selection log."""
    folds = first_rep_folds(p, settings, seed)
    log: dict[str, Any] = {
        "folds": len(folds),
        "metric": "log loss" if p.binary else "squared error",
    }
    chosen = []
    for target in ("outcome", "propensity"):
        losses = {f: fold_losses(p, f, target, folds, settings) for f in settings.families}
        family, entry = one_se_choice(losses)
        if target == "propensity":
            entry["metric"] = "log loss"
        log[target] = entry
        chosen.append(family)
    return (chosen[0], chosen[1]), log


# --- overlap (5.1) -------------------------------------------------------------------


def raw_propensity(
    p: Prepared, dml: Any, family: str, settings: Settings, seed: int = SEED
) -> np.ndarray:
    """The cross-fitted propensity before DoubleML's clipping, shape (n, n_rep).

    DoubleML stores its propensity predictions after clipping them at 0.01/0.99, so the
    propensity learner is refitted on each repetition's folds (``dml.smpls``) with the same
    hyper-parameters and seed; clipping the result gives DoubleML's ``ml_m`` predictions.
    """
    out = np.full((len(p.d), len(dml.smpls)), np.nan)
    for r, folds in enumerate(dml.smpls):
        for train, test in folds:
            model = make_learner(family, "classifier", p.layout, settings, seed)
            model.fit(p.x.iloc[train].to_numpy(), p.d[train])
            out[test, r] = model.predict_proba(p.x.iloc[test].to_numpy())[:, 1]
    return out


def overlap(p: Prepared, raw: np.ndarray) -> dict[str, Any]:
    """5.1 overlap report (author's decision of 2026-10-31), from :func:`raw_propensity`.

    * the quantiles (:data:`OVERLAP_QUANTILES`, unweighted) of the mean cross-fitted
      propensity over repetitions, by exposure group (withheld for a group under 30);
    * the weighted and unweighted share of household x repetition propensities that
      DoubleML clipped at 0.01/0.99;
    * the overlap population: households whose mean propensity lies in [0.01, 0.99]
      (``_inside``), and the share outside it.
    """
    lo, hi = PS_CLIP, 1 - PS_CLIP
    mean = raw.mean(axis=1)
    w = p.frame["pop_wgt"].to_numpy(dtype="float64")
    clipped = (raw < lo) | (raw > hi)
    inside = (mean >= lo) & (mean <= hi)
    quantiles: dict[str, Any] = {}
    for label, arm in (("exposed", 1.0), ("unexposed", 0.0)):
        values = mean[p.d == arm]
        entry: dict[str, Any] = {"households": c.masked(len(values))}
        if len(values) >= c.DISCLOSURE_THRESHOLD:
            entry.update(
                {f"q{round(100 * q):02d}": float(np.quantile(values, q)) for q in OVERLAP_QUANTILES}
            )
        quantiles[label] = entry
    return {
        "propensity": "mean over repetitions of the cross-fitted propensity, before clipping",
        "quantiles_by_exposure": quantiles,
        "clipped_share": {
            "weighted": float((w[:, None] * clipped).sum() / (w.sum() * raw.shape[1])),
            "unweighted": float(clipped.mean()),
        },
        "outside_overlap_population": {
            "households": c.masked(int((~inside).sum())),
            "weighted_share": float(w[~inside].sum() / w.sum()),
            "unweighted_share": float((~inside).mean()),
        },
        "range": [lo, hi],
        "_inside": inside,
    }


def overlap_step(
    p: Prepared, dml: Any, learners: tuple[str, str], settings: Settings
) -> tuple[dict[str, Any], np.ndarray]:
    """The overlap report and the overlap-population mask for the primary fit."""
    report = overlap(p, raw_propensity(p, dml, learners[1], settings))
    inside = report.pop("_inside")
    return report, inside


# --- sensitivity (5.3) ---------------------------------------------------------------


def risk_ratio(ate: float, mu0_value: float) -> float:
    """RR = 1 + ATE / mu0 (5.3)."""
    return 1.0 + ate / mu0_value


def evalue_point(rr: float) -> float:
    """VanderWeele-Ding E-value of a risk ratio; for RR < 1 the E-value of 1/RR."""
    if not np.isfinite(rr) or rr <= 0:
        return float("nan")
    rr = rr if rr >= 1 else 1 / rr
    return float(rr + math.sqrt(rr * (rr - 1)))


def evalue(ate: float, ci_low: float, ci_high: float, mu0_value: float) -> dict[str, float]:
    """E-values for the estimate and for the confidence limit closer to 1 (1 if the
    interval includes RR = 1). The limit ignores the uncertainty in mu0 (5.3 caveat)."""
    rr = risk_ratio(ate, mu0_value)
    lo, hi = risk_ratio(ci_low, mu0_value), risk_ratio(ci_high, mu0_value)
    if lo <= 1 <= hi:
        limit = 1.0
    elif rr >= 1:
        limit = evalue_point(lo)
    else:
        limit = evalue_point(hi)
    return {
        "rr": rr,
        "rr_ci_low": lo,
        "rr_ci_high": hi,
        "evalue": evalue_point(rr),
        "evalue_ci": limit,
    }


def _params(dml: Any) -> dict[str, Any]:
    params = dml.sensitivity_params
    out = {}
    for key in ("theta", "se", "ci"):
        out[key] = {k: float(np.asarray(v).ravel()[0]) for k, v in params[key].items()}
    out["rv"] = float(np.asarray(params["rv"]).ravel()[0])
    out["rva"] = float(np.asarray(params["rva"]).ravel()[0])
    out["input"] = {k: float(v) for k, v in params["input"].items() if isinstance(v, int | float)}
    return out


def sensitivity(dml: Any) -> dict[str, Any]:
    """DoubleML's omitted-variable bounds at its default strengths (cf_y = cf_d = 0.03,
    rho = 1): the bounds and the robustness values RV and RVa."""
    dml.sensitivity_analysis()
    return _params(dml)


def benchmark(
    dml: Any, p: Prepared, learners: tuple[str, str], settings: Settings, names: Sequence[str]
) -> dict[str, Any]:
    """5.3: benchmark the bounds on observed covariates.

    This is DoubleML's ``sensitivity_benchmark`` (a short model refitted without
    ``names`` on the same folds, then ``gain_statistics``), with one change: the short
    model's learners are rebuilt for the shorter column layout, because the learners
    address columns by position. The bounds "a confounder as strong as ``names``" are
    then DoubleML's ``sensitivity_analysis`` at the benchmarked strengths.
    """
    from doubleml.utils.gain_statistics import gain_statistics

    # Each covariate's design columns do not depend on the others, so the short design
    # is a subset of the long one's columns and the data need not change.
    short_p = _short(p, [v for v in p.covariates if v not in names])
    short = copy.deepcopy(dml)
    short._dml_data.x_cols = list(short_p.layout.columns)
    kind_g = "classifier" if p.binary else "regressor"
    short._learner = {
        "ml_g": make_learner(learners[0], kind_g, short_p.layout, settings),
        "ml_m": make_learner(learners[1], "classifier", short_p.layout, settings),
    }
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        try:
            short.fit()
            gains = gain_statistics(dml_long=dml, dml_short=short)
            strengths = {
                k: float(np.asarray(gains[k]).ravel()[0])
                for k in ("cf_y", "cf_d", "rho", "delta_theta")
            }
            out: dict[str, Any] = {
                "dropped": list(names),
                "short_x_cols": list(short._dml_data.x_cols),
                "strengths": strengths,
            }
            cf_y, cf_d, rho = strengths["cf_y"], strengths["cf_d"], strengths["rho"]
            if 0 <= cf_y < 1 and 0 <= cf_d < 1 and -1 <= rho <= 1:
                dml.sensitivity_analysis(cf_y=cf_y, cf_d=cf_d, rho=rho)
                out["bounds"] = _params(dml)
            else:
                out["bounds"] = None
                out["note"] = "benchmarked strengths outside DoubleML's valid range; no bounds"
            dml.sensitivity_analysis()  # restore the default bounds on the object
        finally:
            WARNINGS.add(caught)
    return out


def _short(p: Prepared, covariates: Sequence[str]) -> Prepared:
    frame = p.frame.assign(_y_=p.y, _d_=p.d)
    return prepare(frame, "_y_", "_d_", covariates, p.extra_numeric)


# --- refutations and robustness (5.4) ------------------------------------------------


def permute_within(groups: pd.Series, values: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """``values`` shuffled within each group (the placebo exposure, 5.4.1)."""
    out = values.copy()
    for idx in pd.Series(np.arange(len(values))).groupby(groups.to_numpy()).indices.values():
        out[idx] = values[rng.permutation(idx)]
    return out


def placebo(
    p: Prepared, learners: tuple[str, str], settings: Settings, real: Estimate
) -> dict[str, Any]:
    """5.4.1: the exposure permuted within senatorial district, ``n_placebo`` times;
    n_rep = 1. Expected: centred on 0, about 5% of intervals excluding 0."""
    rng = np.random.default_rng(SEED)
    coefs, excludes = [], []
    for _ in range(settings.n_placebo):
        fake = replace(p, d=permute_within(p.frame["district"], p.d, rng))
        est, _ = fit_irm(fake, learners, settings, n_rep=settings.refutation_n_rep)
        coefs.append(est.coef)
        excludes.append(not (est.ci_low <= 0 <= est.ci_high))
    arr = np.asarray(coefs)
    p_emp = (1 + int((np.abs(arr) >= abs(real.coef)).sum())) / (1 + len(arr))
    return {
        "n": len(arr),
        "mean": float(arr.mean()),
        "sd": float(arr.std(ddof=1)) if len(arr) > 1 else float("nan"),
        "share_ci_excluding_0": float(np.mean(excludes)),
        "empirical_p_real_estimate": float(p_emp),
        "coefs": [float(v) for v in arr],
    }


def rcc_rule(
    reference: float, se: float, moved_to: float, seed_estimates: Sequence[float]
) -> dict[str, Any]:
    """5.4.2: pass if the estimate moves by no more than the larger of 10% of its SE and
    the range of the estimate across the fold seeds."""
    spread = float(np.max(seed_estimates) - np.min(seed_estimates))
    allowed = max(0.1 * se, spread)
    moved = abs(moved_to - reference)
    return {
        "moved": moved,
        "allowed": allowed,
        "seed_range": spread,
        "pass": bool(moved <= allowed),
    }


def random_common_cause(
    p: Prepared, learners: tuple[str, str], settings: Settings
) -> dict[str, Any]:
    """5.4.2: an independent N(0, 1) covariate added; the reference is the n_rep = 1
    estimate with the primary seed; the fold seeds are SEED, SEED + 1, ..."""
    n_rep = settings.refutation_n_rep
    seed_fits = [
        fit_irm(p, learners, settings, n_rep=n_rep, seed=SEED + k)[0]
        for k in range(settings.n_fold_seeds)
    ]
    reference = seed_fits[0]
    noise = np.random.default_rng(SEED).standard_normal(len(p.y))
    frame = p.frame.assign(_y_=p.y, _d_=p.d, random_common_cause=noise)
    with_rcc = prepare(frame, "_y_", "_d_", p.covariates, ("random_common_cause",))
    with_rcc = replace(with_rcc, weights=p.weights, binary=p.binary)
    est, _ = fit_irm(with_rcc, learners, settings, n_rep=n_rep)
    out = rcc_rule(reference.coef, reference.se, est.coef, [f.coef for f in seed_fits])
    out.update(
        {
            "reference": reference.coef,
            "with_random_common_cause": est.coef,
            "seed_estimates": [f.coef for f in seed_fits],
        }
    )
    return out


def subset(p: Prepared, keep: np.ndarray) -> Prepared:
    frame = p.frame.assign(_y_=p.y, _d_=p.d)[keep].reset_index(drop=True)
    return prepare(frame, "_y_", "_d_", p.covariates, p.extra_numeric)


def leave_one_zone_out(
    p: Prepared, learners: tuple[str, str], settings: Settings
) -> dict[str, Any]:
    """5.4.3: the primary analysis with each zone dropped in turn (n_rep = 1); descriptive."""
    out = {}
    for zone in sorted(p.frame["zone"].dropna().unique()):
        keep = (p.frame["zone"] != zone).to_numpy()
        est, _ = fit_irm(subset(p, keep), learners, settings, n_rep=settings.refutation_n_rep)
        out[str(zone)] = est.as_dict()
    return out


def robustness(
    frame: pd.DataFrame, learners: tuple[str, str], settings: Settings
) -> dict[str, Any]:
    """5.4 robustness runs, each with the primary's settings; a failing run records its
    error and the others go on."""
    exposure = EXPOSURES["primary"]
    specs: dict[str, tuple[str, str, tuple[str, str]]] = {
        name: ("poor", name, learners)
        for name in ("no_head_education", "place_head_sex_age", "state_only_place")
    }
    specs.update({f"learners_{f}": ("poor", "primary", (f, f)) for f in settings.families})
    specs.update(
        {
            f"outcome_{outcome}": (outcome, "primary", learners)
            for outcome in ("poor_fuel_alt", "poor_shock_dk0")
        }
    )
    runs: dict[str, Any] = {}
    for name, (outcome, covs, chosen) in specs.items():

        def one(outcome: str = outcome, covs: str = covs, chosen: tuple[str, str] = chosen) -> Any:
            p = prepare(frame, outcome, exposure, COVARIATE_SETS[covs])
            return fit_irm(p, chosen, settings)[0].as_dict()

        runs[name] = attempt(one)
    return runs


# --- secondaries, multiplicity, subgroups (5.5, X1) ----------------------------------


def holm(pvalues: Mapping[str, float]) -> dict[str, float]:
    """Holm's step-down adjusted p-values."""
    items = sorted(pvalues.items(), key=lambda kv: kv[1])
    m = len(items)
    out, running = {}, 0.0
    for i, (name, pv) in enumerate(items):
        running = max(running, min(1.0, (m - i) * pv))
        out[name] = running
    return out


SECONDARIES: dict[str, tuple[str, str, str]] = {
    # name: (outcome, exposure, covariate set)
    "s1_score": ("score", "exposed_primary", "primary"),
    "s2_broad": ("poor", "exposed_s2", "primary"),
    "s3_head": ("poor", "exposed_s3", "no_head_education"),
    **{f"s4_{name}": (name, "exposed_primary", "primary") for name in DIMENSION_OUTCOMES},
    "s5_unasked_severe": ("poor", "exposed_s5", "primary"),
    "s6_routing_free": ("poor", "exposed_s6", "primary"),
}
HOLM_FAMILY = ("s1_score", "s2_broad", "s3_head")


def secondaries(frame: pd.DataFrame, settings: Settings) -> dict[str, Any]:
    """5.5: S1-S6 with their own learner selection; Holm across S1-S3. A failing
    secondary records its error and the others go on; Holm is then not computed (the
    family is incomplete) and the reason is recorded."""
    out: dict[str, Any] = {}
    for name, (outcome, exposure, covs) in SECONDARIES.items():

        def one(outcome: str = outcome, exposure: str = exposure, covs: str = covs) -> Any:
            p = prepare(frame, outcome, exposure, COVARIATE_SETS[covs])
            learners, log = select_learners(p, settings)
            est, _ = fit_irm(p, learners, settings)
            return {"estimate": est.as_dict(), "selection": log}

        out[name] = attempt(one)
    failed = [k for k in HOLM_FAMILY if "error" in out[k]]
    if failed:
        out["holm"] = f"not computed: {', '.join(failed)} failed"
        return out
    adjusted = holm({k: out[k]["estimate"]["pval"] for k in HOLM_FAMILY})
    for name, pv in adjusted.items():
        out[name]["holm_p"] = pv
        out[name]["supported"] = bool(pv < ALPHA)
    return out


def subgroups(frame: pd.DataFrame, learners: tuple[str, str], settings: Settings) -> dict[str, Any]:
    """X1 (exploratory): the primary comparison within urban and rural areas and within
    each zone, with the primary's learners."""
    out = {}
    groups = {
        f"sector={s}": frame["sector"] == s for s in sorted(frame["sector"].dropna().unique())
    }
    groups.update(
        {f"zone={z}": frame["zone"] == z for z in sorted(frame["zone"].dropna().unique())}
    )
    for name, mask in groups.items():

        def one(mask: pd.Series = mask) -> Any:
            p = prepare(
                frame[mask.fillna(False).astype(bool)],
                "poor",
                EXPOSURES["primary"],
                COVARIATE_SETS["primary"],
            )
            return fit_irm(p, learners, settings)[0].as_dict()

        out[name] = attempt(one)  # e.g. no exposed household in a fold
    return out


# --- Table 7 and wording (5.6, 4) ----------------------------------------------------


def table7_check(frame: pd.DataFrame) -> dict[str, Any]:
    """5.6 step 1: the weighted share poor by S2's broad exposure against NBS Table 7
    (71.4% and 61.8%, gap 9.6; each +/- 2.0 points)."""
    keep = frame["poor"].notna() & frame["exposed_s2"].notna()
    sub = frame[keep]
    w, poor, d = sub["pop_wgt"], sub["poor"].astype("float64"), sub["exposed_s2"].astype("float64")
    exposed = 100 * float((w * poor * d).sum() / (w * d).sum())
    unexposed = 100 * float((w * poor * (1 - d)).sum() / (w * (1 - d)).sum())
    values = {"exposed": exposed, "unexposed": unexposed, "gap": exposed - unexposed}
    checks = {k: abs(values[k] - TABLE7[k]) <= TABLE7_TOLERANCE for k in TABLE7}
    return {
        "values": values,
        "published": TABLE7,
        "tolerance": TABLE7_TOLERANCE,
        "pass": checks,
        "all_pass": all(checks.values()),
    }


def wording(est: Estimate) -> str:
    """Section 4's wording rule for the primary estimate."""
    if est.ci_low >= -SMALLEST_DIFFERENCE and est.ci_high <= SMALLEST_DIFFERENCE:
        return "no meaningful difference"
    if est.pval < ALPHA:
        return "difference"
    return "inconclusive"


# --- R benchmark (5.2, 5.3 sensemakr) ------------------------------------------------

R_BENCHMARK = c.ROOT / "packages" / "ingest" / "R" / "p5_benchmark.R"
R_PREFIX = "p5_benchmark.R: "


def r_benchmark(p: Prepared, work: Path) -> dict[str, Any]:
    """Run ``R/p5_benchmark.R``: the survey-weighted LPM (ids = EA, strata = state,
    population weights) and sensemakr on a weighted ``lm``, benchmarked on head education."""
    from curbcut_ingest import aggregate

    work.mkdir(parents=True, exist_ok=True)
    data = p.frame[["cluster", "pop_wgt"]].copy()
    data["state"] = p.frame["state"].astype(str)  # strata (and a covariate when listed)
    data["y"] = p.y
    data["d"] = p.d
    for col in p.covariates:
        if col in CATEGORICAL:
            data[col] = p.frame[col].astype("string").fillna(MISSING_CODE).astype(str)
        elif col == "sector":
            data[col] = p.frame[col].astype(str)
        else:
            data[col] = p.x[col].to_numpy()
    if "head_age_missing" in p.x:
        data["head_age_missing"] = p.x["head_age_missing"].to_numpy()
    input_path, output_path, spec_path = (
        work / "p5_benchmark.input.parquet",
        work / "p5_benchmark.output.json",
        work / "p5_benchmark.spec.json",
    )
    data.to_parquet(input_path, index=False)
    covs = [col for col in p.covariates] + (
        ["head_age_missing"] if "head_age_missing" in p.x else []
    )
    spec = {
        "input": input_path.as_posix(),
        "output": output_path.as_posix(),
        "covariates": covs,
        "categorical": [col for col in covs if col in CATEGORICAL or col == "sector"],
        "benchmark": "head_education",
    }
    spec_path.write_text(json.dumps(spec, indent=2) + "\n", encoding="utf-8", newline="\n")
    aggregate.run_r([aggregate.rscript(), str(R_BENCHMARK), str(spec_path)], prefix=R_PREFIX)
    return json.loads(output_path.read_text(encoding="utf-8"))


# --- synthetic data ------------------------------------------------------------------


@dataclass(frozen=True)
class SyntheticTruth:
    population_effect: float
    """The weighted (population) mean of the household-level risk difference."""
    sample_effect: float
    """The unweighted mean of the same: what ignoring the weights targets."""


def synthetic_households(
    n_clusters: int = 300,
    per_cluster: int = 10,
    seed: int = SEED,
    rural_effect: float = 0.30,
    urban_effect: float = 0.0,
    exposure_scale: float = 1.0,
) -> tuple[pd.DataFrame, SyntheticTruth]:
    """A household analysis frame with the real schema and a KNOWN answer. Invented.

    Confounding: exposure and poverty both rise with the head's age, the number of members
    70+, a lower head education, rural residence and the state. Heterogeneity by a weighted
    stratum: the risk difference is ``rural_effect`` in rural and ``urban_effect`` in urban
    households, and rural households are over-sampled (80% of clusters) with low weights,
    so that people are split about evenly between the sectors. The population-weighted
    and the unweighted average differences therefore differ.
    """
    rng = np.random.default_rng(seed)
    zones = [f"Z{i}" for i in range(1, 7)]
    states = [f"S{i:02d}" for i in range(1, 13)]
    state_zone = {s: zones[i // 2] for i, s in enumerate(states)}
    state_effect = dict(zip(states, rng.normal(0, 0.4, len(states)), strict=True))
    rows = []
    for k in range(n_clusters):
        state = states[k % len(states)]
        district = f"{state}-{1 + (k // len(states)) % 3}"
        rural = rng.random() < 0.8
        for _ in range(per_cluster):
            rows.append(
                {
                    "cluster": f"EA{k:04d}",
                    "state": state,
                    "district": district,
                    "zone": state_zone[state],
                    "sector": "rural" if rural else "urban",
                }
            )
    f = pd.DataFrame(rows)
    n = len(f)
    f["hh_id"] = [f"H{i:05d}" for i in range(n)]
    lam = {
        "n_0_4": 0.9,
        "n_5": 0.2,
        "n_6_14": 1.4,
        "n_15_17": 0.4,
        "n_18_59": 1.6,
        "n_60_69": 0.25,
        "n_70plus": 0.15,
    }
    for col, rate in lam.items():
        f[col] = rng.poisson(rate, n).astype("float64")
    f["n_18_59"] = np.maximum(f["n_18_59"], 1.0)
    f["head_age"] = rng.uniform(20, 85, n).round()
    f.loc[rng.random(n) < 0.01, "head_age"] = np.nan
    f["head_sex"] = np.where(rng.random(n) < 0.8, "male", "female")
    edu_levels = np.array(["none", "primary", "secondary", "higher"])
    f["head_education"] = edu_levels[rng.choice(4, n, p=[0.35, 0.25, 0.3, 0.1])]
    f.loc[rng.random(n) < 0.02, "head_education"] = pd.NA
    rural = (f["sector"] == "rural").to_numpy()
    age = f["head_age"].fillna(50).to_numpy()
    low_edu = f["head_education"].isin(["none", "primary"]).to_numpy()
    st = f["state"].map(state_effect).to_numpy()
    lin = (
        -2.2 + 0.03 * (age - 50) + 0.6 * f["n_70plus"].to_numpy() + 0.5 * low_edu + 0.4 * rural + st
    )
    f["exposed_primary"] = (rng.random(n) < exposure_scale / (1 + np.exp(-lin))).astype("float64")
    base_lin = (
        -0.6
        + 0.015 * (age - 50)
        + 0.3 * f["n_70plus"].to_numpy()
        + 0.7 * low_edu
        + 0.6 * rural
        + 0.8 * st
        + 0.15 * f["n_0_4"].to_numpy()
    )
    base = 0.05 + 0.6 / (1 + np.exp(-base_lin))
    tau = np.where(rural, rural_effect, urban_effect)
    prob = np.clip(base + tau * f["exposed_primary"].to_numpy(), 0, 1)
    f["poor"] = (rng.random(n) < prob).astype("float64")
    size = f[list(lam)].sum(axis=1).to_numpy()
    hh_weight = np.where(rural, 1.0, 4.0) * rng.uniform(0.8, 1.2, n)
    f["pop_wgt"] = hh_weight * size * 100
    # Secondary outcomes and exposures (only their schema matters for the pipeline).
    f["score"] = np.clip(0.2 + 0.35 * prob + rng.normal(0, 0.1, n), 0, 1)
    dims = rng.dirichlet([2, 2, 2, 2], n)
    for (name, _), share in zip(DIMENSION_OUTCOMES.items(), dims.T, strict=True):
        f[name] = f["score"] * share
    f["poor_fuel_alt"] = np.where(rng.random(n) < 0.95, f["poor"], 1 - f["poor"])
    f["poor_shock_dk0"] = f["poor"]
    f["exposed_s2"] = np.maximum(f["exposed_primary"], (rng.random(n) < 0.12).astype("float64"))
    f["exposed_s3"] = f["exposed_primary"] * (rng.random(n) < 0.5)
    f["exposed_s5"] = np.maximum(f["exposed_primary"], (rng.random(n) < 0.06).astype("float64"))
    f["exposed_s6"] = f["exposed_primary"] * (rng.random(n) < 0.7)
    f.loc[rng.random(n) < 0.01, "poor"] = np.nan
    w = f["pop_wgt"].to_numpy()
    truth = SyntheticTruth(
        population_effect=float((w * tau).sum() / w.sum()), sample_effect=float(tau.mean())
    )
    for col in ("state", "district", "zone", "sector", "cluster", "head_sex", "head_education"):
        f[col] = f[col].astype("string")
    for col in ("poor", "score", "head_age", *EXPOSURES.values()):
        f[col] = f[col].astype("Float64")
    return f, truth


# --- run, manifest -------------------------------------------------------------------


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_commit() -> dict[str, Any]:
    def git(*args: str) -> str:
        result = subprocess.run(
            ["git", *args], cwd=c.ROOT, capture_output=True, text=True, check=False
        )
        return result.stdout.strip()

    return {"commit": git("rev-parse", "HEAD"), "dirty": bool(git("status", "--porcelain"))}


PACKAGES = ("doubleml", "scikit-learn", "numpy", "pandas", "scipy", "pyfixest", "pyarrow")


def manifest(
    mode: str,
    settings: Settings,
    inputs: Mapping[str, Path],
    selection: Mapping[str, Any],
    elapsed: float,
    warning_counts: Mapping[str, int] | None = None,
    status: str = "complete",
) -> dict[str, Any]:
    """Section 9: package versions, seeds, commit, input file hashes, the selection log,
    the warnings counted while fitting, and :data:`NOTES`."""
    versions = {}
    for name in PACKAGES:
        try:
            versions[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            versions[name] = None
    return {
        "mode": mode,
        "created": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
        "python": platform.python_version(),
        "packages": versions,
        "seed": SEED,
        "settings": asdict(settings),
        "git": git_commit(),
        "inputs": {
            name: {"path": path.name, "sha256": sha256(path)} for name, path in inputs.items()
        },
        "preregistration_sha256": sha256(PREREG) if PREREG.is_file() else None,
        "learner_selection": selection,
        "warnings": dict(warning_counts or {}),
        "notes": list(NOTES),
        "status": status,
        "elapsed_seconds": round(elapsed, 1),
    }


def _json_default(value: Any) -> Any:
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, tuple):
        return list(value)
    raise TypeError(type(value).__name__)


def write_json(data: Mapping[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    clean = {k: v for k, v in data.items() if not str(k).startswith("_")}
    path.write_text(
        json.dumps(clean, indent=2, default=_json_default) + "\n", encoding="utf-8", newline="\n"
    )


Step = Callable[[], Any]


def run(
    frame: pd.DataFrame,
    settings: Settings,
    with_r: bool = True,
    work: Path | None = None,
    log: Callable[[str], None] = c.log,
    checkpoint: Callable[[Mapping[str, Any]], None] | None = None,
) -> dict[str, Any]:
    """The whole MPI analysis in the pre-registered order (5.6, after registration).

    ``checkpoint`` is called with the results so far after every step (``main`` writes
    ``results.json`` and the manifest there). Steps 1-3 up to the primary estimate must
    succeed; every later step is wrapped (:func:`attempt`) and records its error instead.
    """
    results: dict[str, Any] = {"status": "running"}
    WARNINGS.counts.clear()

    def save() -> None:
        results["warnings"] = WARNINGS.as_dict()
        if checkpoint is not None:
            checkpoint(results)

    def step(key: str, func: Callable[[], Any]) -> Any:
        results[key] = attempt(func)
        save()
        return results[key]

    log("step 1: Table 7 check")
    step("table7", lambda: table7_check(frame))
    p = prepare(frame, "poor", EXPOSURES["primary"], COVARIATE_SETS["primary"])
    results["weights"] = kish(p.frame["pop_wgt"])
    log("step 2: learner selection")
    learners, selection = select_learners(p, settings)
    results["learner_selection"] = selection
    save()
    log(f"  chosen: outcome {learners[0]}, propensity {learners[1]}")
    log("step 3: primary estimate")
    est, dml = fit_irm(p, learners, settings)
    results["primary"] = est.as_dict()
    results["primary"]["wording"] = wording(est)
    results["evalue"] = evalue(est.coef, est.ci_low, est.ci_high, est.mu0)
    save()

    log("  overlap")
    overlap_mask: list[np.ndarray] = []

    def overlap_report() -> dict[str, Any]:
        report, inside = overlap_step(p, dml, learners, settings)
        overlap_mask.append(inside)
        return report

    step("overlap", overlap_report)
    if overlap_mask:
        step(
            "overlap_population",
            lambda: fit_irm(subset(p, overlap_mask[0]), learners, settings)[0].as_dict(),
        )
    else:
        results["overlap_population"] = {
            "error": "NotRun",
            "message": "not run: the overlap report failed",
        }
    log("  sensitivity: bounds and benchmarks")
    results["sensitivity"] = {"default": attempt(lambda: sensitivity(dml)), "benchmarks": {}}
    save()
    for name, cols in BENCHMARKS.items():
        results["sensitivity"]["benchmarks"][name] = attempt(
            lambda cols=cols: benchmark(dml, p, learners, settings, cols)
        )
        save()
    if with_r:
        log("  R: survey LPM and sensemakr")
        step("r_benchmark", lambda: r_benchmark(p, work or OUT_DIR / "work"))
    log("  refutations")
    refutations: dict[str, Callable[[], Any]] = {
        "placebo": lambda: placebo(p, learners, settings, est),
        "random_common_cause": lambda: random_common_cause(p, learners, settings),
        "leave_one_zone_out": lambda: leave_one_zone_out(p, learners, settings),
    }
    results["refutations"] = {}
    for name, func in refutations.items():
        results["refutations"][name] = attempt(func)
        save()
    log("  robustness")
    step("robustness", lambda: robustness(frame, learners, settings))
    log("step 4: secondaries and X1")
    step("secondaries", lambda: secondaries(frame, settings))
    step("x1_subgroups", lambda: subgroups(frame, learners, settings))
    results["failed_steps"] = failed_steps(results)
    results["status"] = "complete_with_errors" if results["failed_steps"] else "complete"
    save()
    return results


def load_real(derived: Path) -> tuple[pd.DataFrame, dict[str, Any], dict[str, Path]]:
    """The real analysis frame. Guarded here too, not only in :func:`main`: refused
    (:class:`RegistrationError`) until the pre-registration is registered."""
    require_registration(PREREG)
    inputs = {
        "households": derived / f"{HOUSEHOLD_NAME}.parquet",
        "exposure": derived / f"{EXPOSURE_NAME}.parquet",
    }
    frame, summary = analysis_frame(
        pd.read_parquet(inputs["households"]), pd.read_parquet(inputs["exposure"])
    )
    return frame, summary, inputs


@c.safe_main
def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="P5 MPI analysis (synthetic by default).")
    parser.add_argument(
        "--real", action="store_true", help="run on the real files (refused until OSF registration)"
    )
    parser.add_argument("--quick", action="store_true", help="synthetic only: smaller run sizes")
    parser.add_argument("--no-r", action="store_true", help="skip the R benchmark")
    parser.add_argument("--derived", type=Path, default=c.DERIVED)
    parser.add_argument("--out-dir", type=Path, default=None)
    parser.add_argument("--n-clusters", type=int, default=300, help="synthetic only")
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
            url = require_registration(PREREG)
        except RegistrationError as exc:
            c.log(f"refused: {exc}")  # the message names the rule, never data
            return 1
        if args.quick:
            raise SystemExit("--quick is for synthetic runs only")
        settings = PREREGISTERED
        c.log(f"P5 MPI: real data (registered: {url})")
        frame, summary, inputs = load_real(args.derived)
        out_dir = args.out_dir or OUT_DIR
        mode = "real"
    else:
        settings = QUICK if args.quick else PREREGISTERED
        c.log("P5 MPI: SYNTHETIC data (invented; no real file is read)")
        frame, truth = synthetic_households(n_clusters=args.n_clusters)
        summary = {"synthetic_truth": asdict(truth), "households": len(frame)}
        out_dir = args.out_dir or OUT_DIR / "synthetic"
        work = out_dir / "work"
        work.mkdir(parents=True, exist_ok=True)
        synthetic_path = work / "synthetic_households.parquet"
        frame.to_parquet(synthetic_path, index=False)
        inputs = {"synthetic_households": synthetic_path}
        mode = "synthetic-quick" if args.quick else "synthetic"

    def checkpoint(results: Mapping[str, Any]) -> None:
        """Rewrite results.json and the manifest after every step."""
        write_json({**results, "sample": summary}, out_dir / "results.json")
        write_json(
            manifest(
                mode,
                settings,
                inputs,
                results.get("learner_selection", {}),
                time.perf_counter() - start,
                results.get("warnings", {}),
                str(results.get("status", "running")),
            ),
            out_dir / "manifest.json",
        )

    results = run(
        frame, settings, with_r=not args.no_r, work=out_dir / "work", checkpoint=checkpoint
    )
    results["sample"] = summary
    elapsed = time.perf_counter() - start
    c.log(f"wrote results.json and manifest.json ({elapsed:.0f} s)")
    if results["failed_steps"]:
        c.log(f"{len(results['failed_steps'])} steps failed: {', '.join(results['failed_steps'])}")
    if mode != "real":
        primary = results["primary"]
        truth = summary["synthetic_truth"]["population_effect"]
        c.log(
            f"  synthetic primary: {primary['coef']:.3f} "
            f"[{primary['ci_low']:.3f}, {primary['ci_high']:.3f}]; truth {truth:.3f}"
        )
    return 1 if results["failed_steps"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
