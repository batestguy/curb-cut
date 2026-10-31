"""P5 MPI analysis (pre-registration sections 3-7) on SYNTHETIC data only.

Nothing here reads ``data/restricted/``: every frame is made by
:func:`p5_mpi.synthetic_households` or written out by hand. The DoubleML runs use small
samples and one repetition so that the suite stays fast; the pre-registered sizes are in
:data:`p5_mpi.PREREGISTERED` and are checked separately.
"""

from __future__ import annotations

import math
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest
from curbcut_ingest.restricted import common as c
from curbcut_ingest.restricted import p5_mpi as m

FAST = m.Settings(
    n_rep=1, n_placebo=5, n_fold_seeds=2, forest_trees=20, boosting_iter=20, families=("logistic",)
)


@pytest.fixture(scope="module")
def households() -> tuple[pd.DataFrame, m.SyntheticTruth]:
    return m.synthetic_households(n_clusters=300, per_cluster=10)


@pytest.fixture(scope="module")
def small() -> pd.DataFrame:
    frame, _ = m.synthetic_households(n_clusters=80, per_cluster=10, seed=7)
    return frame


@pytest.fixture(scope="module")
def fitted(small: pd.DataFrame) -> tuple[m.Prepared, m.Estimate, object]:
    p = m.prepare(small, "poor", "exposed_primary", m.COVARIATE_SETS["primary"])
    est, dml = m.fit_irm(p, ("logistic", "logistic"), FAST)
    return p, est, dml


# --- the pre-registered constants ----------------------------------------------------


def test_preregistered_settings() -> None:
    s = m.PREREGISTERED
    assert (s.n_folds, s.n_rep, s.refutation_n_rep, s.n_placebo, s.n_fold_seeds) == (
        5,
        5,
        1,
        100,
        5,
    )
    assert (s.forest_trees, s.boosting_iter) == (500, 300)
    assert s.families == ("logistic", "forest", "boosting")
    assert m.SEED == 20261030
    assert m.PS_CLIP == 0.01
    assert m.OVERLAP_QUANTILES == (0.01, 0.05, 0.25, 0.5, 0.75, 0.95, 0.99)
    assert m.BENCHMARKS == {
        "head_education": ["head_education"],
        "place": ["state", "district"],
        "sector": ["sector"],
    }
    assert m.COUNTS == ("n_0_4", "n_5", "n_6_14", "n_15_17", "n_18_59", "n_60_69", "n_70plus")
    assert "head_education" not in m.COVARIATE_SETS["no_head_education"]
    assert m.SECONDARIES["s3_head"][2] == "no_head_education"
    assert m.COVARIATE_SETS["place_head_sex_age"] == (
        "state",
        "district",
        "sector",
        "head_sex",
        "head_age",
    )
    assert "district" not in m.COVARIATE_SETS["state_only_place"]


def test_learner_hyperparameters() -> None:
    layout = m.Layout(("state", "head_age", "n_5"), ("state",), ("head_age",), ("n_5",))
    logistic = m.make_learner("logistic", "classifier", layout)
    assert logistic.named_steps["model"].C == 1.0
    forest = m.make_learner("forest", "classifier", layout).named_steps["model"]
    assert (forest.n_estimators, forest.min_samples_leaf, forest.max_features) == (500, 20, "sqrt")
    assert forest.random_state == m.SEED
    boost = m.make_learner("boosting", "classifier", layout)
    assert (boost.max_iter, boost.learning_rate, boost.max_leaf_nodes, boost.min_samples_leaf) == (
        300, 0.05, 31, 50)  # fmt: skip
    assert boost.early_stopping is False
    assert boost.categorical_features == [0]


def test_natural_spline_is_linear_beyond_the_boundary_knots() -> None:
    x = np.linspace(0, 100, 501)[:, None]
    spline = m.NaturalCubicSpline(5).fit(x)
    assert len(spline.knots_) == 5
    basis = spline.transform(np.array([[200.0], [300.0], [400.0]]))
    # Beyond the last knot every column is linear in x: equal second differences of 0.
    assert np.allclose(basis[2] - 2 * basis[1] + basis[0], 0, atol=1e-9)


# --- weights and frame (3.1) ---------------------------------------------------------


def test_weights_normalised_and_kish() -> None:
    w = np.array([1.0, 1.0, 2.0, 4.0])
    assert m.normalised_weights(w).mean() == pytest.approx(1.0)
    k = m.kish(w)
    assert k["kish_effective_n"] == pytest.approx(64 / 22)
    assert k["max_weight_share"] == pytest.approx(0.5)


def test_design_has_missing_categories_and_age_indicator(small: pd.DataFrame) -> None:
    x, layout = m.design(small, m.COVARIATE_SETS["primary"])
    assert "head_age_missing" in layout.numeric  # synthetic data have missing head ages
    assert not x.isna().any().any()
    assert layout.categorical == ("state", "district", "head_sex", "head_education")


# --- the estimator (5.1) -------------------------------------------------------------


def test_known_population_effect_recovered_and_weights_matter(
    households: tuple[pd.DataFrame, m.SyntheticTruth],
) -> None:
    """The weighted estimate covers the population-weighted truth; ignoring the weights
    targets the sample average instead, which differs because the effect is
    heterogeneous by an over-sampled stratum."""
    frame, truth = households
    assert truth.sample_effect - truth.population_effect > 0.05
    p = m.prepare(frame, "poor", "exposed_primary", m.COVARIATE_SETS["primary"])
    weighted, _ = m.fit_irm(p, ("logistic", "logistic"), FAST)
    unweighted, _ = m.fit_irm(p, ("logistic", "logistic"), FAST, weighted=False)
    assert weighted.ci_low <= truth.population_effect <= weighted.ci_high
    assert abs(unweighted.coef - truth.sample_effect) < abs(
        unweighted.coef - truth.population_effect
    )
    assert unweighted.coef - weighted.coef > 0.03


def test_folds_respect_clusters(fitted: tuple[m.Prepared, m.Estimate, object]) -> None:
    p, _, dml = fitted
    for train, test in dml.smpls[0]:  # type: ignore[attr-defined]
        assert not set(p.cluster[train]) & set(p.cluster[test])
    folds = m.first_rep_folds(p, FAST)
    assert len(folds) == 5
    for train, test in folds:
        assert not set(p.cluster[train]) & set(p.cluster[test])


def test_seed_makes_runs_reproducible(fitted: tuple[m.Prepared, m.Estimate, object]) -> None:
    p, est, _ = fitted
    again, _ = m.fit_irm(p, ("logistic", "logistic"), FAST)
    assert again.coef == est.coef and again.se == est.se
    other, _ = m.fit_irm(p, ("logistic", "logistic"), FAST, seed=m.SEED + 1)
    assert other.coef != est.coef  # a different fold seed gives a different split
    assert [tuple(t) for _, t in m.first_rep_folds(p, FAST)] == [
        tuple(t) for _, t in m.first_rep_folds(p, FAST)]  # fmt: skip


def test_mu0_is_the_weighted_doubly_robust_untreated_mean() -> None:
    # Hand values: 4 units, 1 repetition; g0 and m as given; weights normalised.
    y = np.array([1.0, 0.0, 1.0, 0.0])
    d = np.array([0.0, 0.0, 1.0, 0.0])
    g0 = np.array([0.5, 0.5, 0.5, 0.5])
    ps = np.array([0.5, 0.5, 0.5, 0.5])
    w = np.array([1.0, 1.0, 1.0, 1.0])
    p = SimpleNamespace(y=y, d=d, weights=w)
    dml = SimpleNamespace(predictions={"ml_g0": g0[:, None, None], "ml_m": ps[:, None, None]})
    # Unexposed: residuals +0.5, -0.5, -0.5 with h = 2 each; correction = -0.5*2 / 6.
    expected = 0.5 + (2 * (0.5 - 0.5 - 0.5)) / 6
    assert m.mu0(dml, p) == pytest.approx(expected)  # type: ignore[arg-type]


@pytest.mark.parametrize("family", m.PREFERENCE)
def test_raw_propensity_reproduces_doubleml_before_clipping(
    small: pd.DataFrame, family: str
) -> None:
    # The overlap population is defined on this refit, so it must be DoubleML's own
    # propensity model for every family, not only the logistic one.
    p = m.prepare(small, "poor", "exposed_primary", m.COVARIATE_SETS["primary"])
    _, dml = m.fit_irm(p, ("logistic", family), FAST)
    raw = m.raw_propensity(p, dml, family, FAST)
    assert raw.shape == (len(p.y), FAST.n_rep) and not np.isnan(raw).any()
    stored = np.asarray(dml.predictions["ml_m"])[:, :, 0]  # type: ignore[attr-defined]
    assert np.allclose(np.clip(raw, m.PS_CLIP, 1 - m.PS_CLIP), stored)


def test_failed_steps_lists_every_recorded_error() -> None:
    results = {
        "primary": {"coef": 0.1},
        "refutations": {"placebo": m.error_entry(ValueError("only 3 clusters")), "rcc": {}},
        "secondaries": [{"name": "S1"}, m.error_entry(RuntimeError("x"))],
    }
    assert m.failed_steps(results) == ["refutations.placebo", "secondaries[1]"]
    assert m.failed_steps({"primary": {"coef": 0.1}}) == []


def test_overlap_report_on_hand_values() -> None:
    # Six households, two repetitions; mean propensities 0.005, 0.5, 0.995, 0.3, 0.2, 0.6.
    raw = np.array([[0.004, 0.006], [0.5, 0.5], [0.99, 1.0], [0.3, 0.3], [0.2, 0.2], [0.6, 0.6]])
    d = np.array([0.0, 0.0, 1.0, 1.0, 0.0, 1.0])
    frame = pd.DataFrame({"pop_wgt": [1.0, 1.0, 2.0, 1.0, 1.0, 2.0]})
    p = SimpleNamespace(frame=frame, d=d)
    out = m.overlap(p, raw)  # type: ignore[arg-type]
    assert out["_inside"].tolist() == [False, True, False, True, True, True]
    outside = out["outside_overlap_population"]
    assert outside["weighted_share"] == pytest.approx(3 / 8)
    assert outside["unweighted_share"] == pytest.approx(2 / 6)
    # Clipped household x repetition cells: (0, 0), (0, 1) and (2, 1) of 12.
    assert out["clipped_share"]["unweighted"] == pytest.approx(3 / 12)
    assert out["clipped_share"]["weighted"] == pytest.approx((1 + 1 + 2) / (8 * 2))
    # Groups under 30 households: counts masked, quantiles withheld.
    assert out["quantiles_by_exposure"]["exposed"] == {"households": "<30"}


def test_overlap_quantiles_by_exposure_group() -> None:
    rng = np.random.default_rng(0)
    raw = rng.uniform(0.02, 0.98, (200, 1))
    d = (np.arange(200) < 100).astype(float)
    p = SimpleNamespace(frame=pd.DataFrame({"pop_wgt": np.ones(200)}), d=d)
    q = m.overlap(p, raw)["quantiles_by_exposure"]  # type: ignore[arg-type]
    assert set(q["exposed"]) == {"households", "q01", "q05", "q25", "q50", "q75", "q95", "q99"}
    assert q["exposed"]["q50"] == pytest.approx(float(np.median(raw[:100, 0])))
    assert q["unexposed"]["q25"] == pytest.approx(float(np.quantile(raw[100:, 0], 0.25)))


# --- learner selection (5.1) ---------------------------------------------------------


def test_one_se_rule_prefers_the_simpler_learner() -> None:
    # Boosting is lowest, but logistic is within one SE of it -> logistic.
    losses = {
        "logistic": [0.51, 0.50, 0.50, 0.51, 0.49],
        "forest": [0.6] * 5,
        "boosting": [0.50, 0.48, 0.52, 0.51, 0.49],
    }
    chosen, log = m.one_se_choice(losses)
    assert log["lowest"] == "boosting"
    assert chosen == "logistic"
    # Logistic clearly worse; forest within one SE -> forest (before boosting).
    losses = {
        "logistic": [0.7] * 5,
        "forest": [0.501, 0.49, 0.51, 0.50, 0.50],
        "boosting": [0.50, 0.49, 0.51, 0.50, 0.495],
    }
    assert m.one_se_choice(losses)[0] == "forest"
    # Nothing within one SE of the best -> the best.
    losses = {
        "logistic": [0.7] * 5,
        "forest": [0.6] * 5,
        "boosting": [0.50, 0.49, 0.51, 0.50, 0.50],
    }
    assert m.one_se_choice(losses)[0] == "boosting"


def test_select_learners_logs_both_models(small: pd.DataFrame) -> None:
    p = m.prepare(small, "poor", "exposed_primary", m.COVARIATE_SETS["primary"])
    settings = m.Settings(n_rep=1, forest_trees=10, boosting_iter=10)
    (outcome, propensity), log = m.select_learners(p, settings)
    assert outcome in settings.families and propensity in settings.families
    assert set(log["outcome"]["candidates"]) == set(settings.families)
    assert log["metric"] == "log loss" and log["folds"] == 5


# --- sensitivity (5.3) ---------------------------------------------------------------


def test_sensitivity_runs_with_weights_and_clusters(
    fitted: tuple[m.Prepared, m.Estimate, object],
) -> None:
    """Pre-registration 5.3 promises this test: the bounds and the benchmarks run on a
    model fitted with survey weights and cluster-based folds."""
    p, est, dml = fitted
    assert dml._dml_data.cluster_cols == ["_cluster"]  # type: ignore[attr-defined]
    assert dml.weights is not None  # type: ignore[attr-defined]
    sens = m.sensitivity(dml)
    assert sens["theta"]["lower"] <= est.coef <= sens["theta"]["upper"]
    assert 0 <= sens["rv"] <= 1
    before = (
        dml.coef.copy(),  # type: ignore[attr-defined]
        dml.se.copy(),  # type: ignore[attr-defined]
        list(dml._dml_data.x_cols),  # type: ignore[attr-defined]
    )
    for name, cols in m.BENCHMARKS.items():
        out = m.benchmark(dml, p, ("logistic", "logistic"), FAST, cols)
        assert set(out["strengths"]) == {"cf_y", "cf_d", "rho", "delta_theta"}, name
        # The short model lacks exactly the benchmarked covariates' columns.
        assert not set(cols) & set(out["short_x_cols"]), name
        assert set(out["short_x_cols"]) < set(before[2]), name
    # The primary object is unchanged after every benchmark.
    assert np.array_equal(dml.coef, before[0])  # type: ignore[attr-defined]
    assert np.array_equal(dml.se, before[1])  # type: ignore[attr-defined]
    assert list(dml._dml_data.x_cols) == before[2]  # type: ignore[attr-defined]
    assert dml.coef[0] == est.coef  # type: ignore[attr-defined]


def test_place_benchmark_drops_state_and_district(
    fitted: tuple[m.Prepared, m.Estimate, object],
) -> None:
    p, _, dml = fitted
    out = m.benchmark(dml, p, ("logistic", "logistic"), FAST, m.BENCHMARKS["place"])
    assert "state" not in out["short_x_cols"] and "district" not in out["short_x_cols"]
    assert "sector" in out["short_x_cols"] and out["dropped"] == ["state", "district"]


def test_evalue_against_hand_values() -> None:
    assert m.evalue_point(2.0) == pytest.approx(2 + math.sqrt(2))
    assert m.evalue_point(0.5) == pytest.approx(2 + math.sqrt(2))  # 1/RR for RR < 1
    assert m.evalue_point(1.0) == pytest.approx(1.0)
    assert m.evalue_point(1.2) == pytest.approx(1.2 + math.sqrt(1.2 * 0.2))
    assert m.risk_ratio(0.1, 0.5) == pytest.approx(1.2)
    out = m.evalue(0.1, 0.05, 0.15, 0.5)
    assert out["rr"] == pytest.approx(1.2)
    assert out["evalue_ci"] == pytest.approx(m.evalue_point(1.1))  # the limit closer to 1
    assert m.evalue(0.1, -0.02, 0.2, 0.5)["evalue_ci"] == 1.0  # interval includes RR = 1
    below = m.evalue(-0.1, -0.15, -0.05, 0.5)
    assert below["rr"] == pytest.approx(0.8)
    assert below["evalue"] == pytest.approx(m.evalue_point(1 / 0.8))
    assert below["evalue_ci"] == pytest.approx(m.evalue_point(1 / 0.9))


# --- refutations, multiplicity (5.4, 5.5) --------------------------------------------


def test_placebo_centred_on_zero_on_null_data() -> None:
    frame, truth = m.synthetic_households(n_clusters=80, per_cluster=10, seed=11, rural_effect=0.0)
    assert truth.population_effect == 0.0
    p = m.prepare(frame, "poor", "exposed_primary", m.COVARIATE_SETS["primary"])
    settings = m.Settings(n_rep=1, n_placebo=8, families=("logistic",))
    real, _ = m.fit_irm(p, ("logistic", "logistic"), settings)
    out = m.placebo(p, ("logistic", "logistic"), settings, real)
    assert out["n"] == 8
    assert abs(out["mean"]) < 3 * out["sd"] / math.sqrt(out["n"]) + 0.01
    assert 0 < out["empirical_p_real_estimate"] <= 1


def test_permutation_stays_within_district() -> None:
    groups = pd.Series(["a", "a", "a", "b", "b"])
    values = np.array([1.0, 0.0, 0.0, 1.0, 1.0])
    out = m.permute_within(groups, values, np.random.default_rng(1))
    assert out[:3].sum() == 1 and out[3:].sum() == 2


def test_random_common_cause_rule() -> None:
    # Allowed = max(10% of SE, range across fold seeds).
    assert m.rcc_rule(0.10, 0.02, 0.101, [0.10, 0.1005])["pass"]  # moved 0.001 <= 0.002
    assert not m.rcc_rule(0.10, 0.02, 0.105, [0.10, 0.101])["pass"]  # 0.005 > max(0.002, 0.001)
    out = m.rcc_rule(0.10, 0.02, 0.105, [0.098, 0.106])
    assert out["allowed"] == pytest.approx(0.008) and out["pass"]


def test_random_common_cause_runs(fitted: tuple[m.Prepared, m.Estimate, object]) -> None:
    p, _, _ = fitted
    out = m.random_common_cause(p, ("logistic", "logistic"), FAST)
    assert len(out["seed_estimates"]) == FAST.n_fold_seeds
    assert out["reference"] == out["seed_estimates"][0]


def test_holm_against_hand_values() -> None:
    adjusted = m.holm({"s1": 0.01, "s2": 0.04, "s3": 0.03})
    assert adjusted == pytest.approx({"s1": 0.03, "s3": 0.06, "s2": 0.06})
    assert m.holm({"a": 0.5, "b": 0.9}) == pytest.approx({"a": 1.0, "b": 1.0})


def test_wording_rule() -> None:
    def est(lo: float, hi: float, p: float) -> m.Estimate:
        return m.Estimate(
            (lo + hi) / 2, 0.01, lo, hi, p, 10, "10", [], 0.6, ("logistic", "logistic"), 1
        )

    assert m.wording(est(-0.015, 0.019, 0.5)) == "no meaningful difference"
    assert m.wording(est(0.01, 0.05, 0.01)) == "difference"
    assert m.wording(est(-0.01, 0.05, 0.2)) == "inconclusive"


# --- Table 7 check (5.6) -------------------------------------------------------------


def test_table7_check() -> None:
    # Exposed: 7 of 10 people poor (70%); unexposed: 62 of 100 (62%); gap 8.
    frame = pd.DataFrame(
        {
            "pop_wgt": [7.0, 3.0, 62.0, 38.0, 5.0],
            "poor": pd.array([1, 0, 1, 0, pd.NA], dtype="Float64"),
            "exposed_s2": pd.array([1, 1, 0, 0, 1], dtype="Float64"),
        }
    )
    out = m.table7_check(frame)
    assert out["values"]["exposed"] == pytest.approx(70.0)
    assert out["values"]["unexposed"] == pytest.approx(62.0)
    assert out["values"]["gap"] == pytest.approx(8.0)
    assert out["pass"] == {"exposed": True, "unexposed": True, "gap": True}
    frame.loc[0, "pop_wgt"] = 9.0  # exposed 75% -> outside 71.4 +/- 2; gap 13 -> outside
    out = m.table7_check(frame)
    assert out["pass"]["exposed"] is False and out["pass"]["gap"] is False
    assert out["all_pass"] is False


# --- the real-data guard (rule: nothing on real data before OSF) ---------------------


PREREG_TEXT = (
    "# Pre-registration\n\n## 10. Deviations\n\nSee https://osf.io/abcde/ maybe.\n\n"
    "## 11. Registration record\n\n{body}\n"
)


def test_registration_url_only_from_section_11(tmp_path: Path) -> None:
    assert m.registration_url(PREREG_TEXT.format(body="To be filled at registration.")) is None
    filled = PREREG_TEXT.format(body="OSF: https://osf.io/xyz12 (2026-11-02)")
    assert m.registration_url(filled) == "https://osf.io/xyz12"
    path = tmp_path / "prereg.md"
    path.write_text(PREREG_TEXT.format(body="pending"), encoding="utf-8")
    with pytest.raises(m.RegistrationError):
        m.require_registration(path)
    with pytest.raises(m.RegistrationError):
        m.require_registration(tmp_path / "missing.md")
    path.write_text(filled, encoding="utf-8")
    assert m.require_registration(path) == "https://osf.io/xyz12"


def test_real_mode_refused_without_registration(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    path = tmp_path / "prereg.md"
    path.write_text(PREREG_TEXT.format(body="pending"), encoding="utf-8")
    monkeypatch.setattr(m, "PREREG", path)
    monkeypatch.setattr(m.require_registration, "__defaults__", (path,))

    def boom(*_: object) -> None:
        raise AssertionError("real files must not be read")

    monkeypatch.setattr(m, "load_real", boom)
    assert m.main(["--real", "--derived", str(tmp_path)]) == 1  # refused, message withheld
    assert not (tmp_path / "p5").exists()


def test_load_real_is_guarded_too(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Defence in depth: load_real refuses by itself, before any file is opened."""
    path = tmp_path / "prereg.md"
    path.write_text(PREREG_TEXT.format(body="pending"), encoding="utf-8")
    monkeypatch.setattr(m, "PREREG", path)

    def boom(*_: object, **__: object) -> None:
        raise AssertionError("real files must not be read")

    monkeypatch.setattr(pd, "read_parquet", boom)
    with pytest.raises(m.RegistrationError):
        m.load_real(tmp_path)


def test_out_dir_must_be_in_the_restricted_zone(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(c, "RESTRICTED", tmp_path / "restricted")

    def boom(*_: object, **__: object) -> None:
        raise AssertionError("nothing may run before the out-dir check")

    monkeypatch.setattr(m, "synthetic_households", boom)
    assert m.main(["--quick", "--no-r", "--out-dir", str(tmp_path / "public")]) == 2
    assert not (tmp_path / "public").exists()


def test_current_preregistration_is_not_registered() -> None:
    """While docs/preregistration.md has no OSF URL, real mode must stay refused."""
    if m.PREREG.is_file() and m.registration_url(m.PREREG.read_text(encoding="utf-8")) is None:
        with pytest.raises(m.RegistrationError):
            m.require_registration()


# --- the whole pipeline on synthetic data --------------------------------------------


def test_run_end_to_end_on_synthetic_data(tmp_path: Path) -> None:
    frame, _ = m.synthetic_households(n_clusters=60, per_cluster=10, seed=3)
    settings = m.Settings(
        n_rep=1,
        n_placebo=2,
        n_fold_seeds=2,
        forest_trees=10,
        boosting_iter=10,
        families=("logistic",),
    )
    saved: list[str] = []
    results = m.run(
        frame,
        settings,
        with_r=False,
        work=tmp_path,
        log=lambda _: None,
        checkpoint=lambda r: saved.append(str(r.get("status"))),
    )
    for key in (
        "table7",
        "weights",
        "learner_selection",
        "primary",
        "overlap",
        "overlap_population",
        "evalue",
        "sensitivity",
        "refutations",
        "robustness",
        "secondaries",
        "x1_subgroups",
        "warnings",
    ):
        assert key in results, key
    assert results["status"] == "complete" and results["failed_steps"] == []
    assert len(saved) > 10 and saved[0] == "running" and saved[-1] == "complete"
    assert "coef" in results["overlap_population"]  # always run (5.1, 2026-10-31)
    assert set(results["secondaries"]["s1_score"]) >= {"holm_p", "supported", "estimate"}
    assert "holm_p" not in results["secondaries"]["s5_unasked_severe"]
    assert set(results["sensitivity"]["benchmarks"]) == {"head_education", "place", "sector"}
    assert len(results["refutations"]["leave_one_zone_out"]) == 6
    assert {f"learners_{f}" for f in settings.families} <= set(results["robustness"])
    m.write_json(results, tmp_path / "results.json")
    out = m.manifest(
        "synthetic",
        settings,
        {"x": tmp_path / "results.json"},
        results["learner_selection"],
        1.0,
        results["warnings"],
    )
    assert out["seed"] == m.SEED and out["inputs"]["x"]["sha256"]
    assert out["packages"]["doubleml"] is not None
    assert any("normalize_ipw" in note for note in out["notes"])
    assert out["warnings"] == results["warnings"]


def test_failing_late_steps_do_not_end_the_run(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """R1: a late failure is recorded (type and message template, numbers removed) and
    earlier results are already on disk."""
    frame, _ = m.synthetic_households(n_clusters=60, per_cluster=10, seed=3)
    settings = m.Settings(
        n_rep=1, n_placebo=2, n_fold_seeds=2, forest_trees=10, boosting_iter=10,
        families=("logistic",),
    )  # fmt: skip
    real_fit = m.fit_irm

    def fit_or_fail(p: m.Prepared, *args: object, **kwargs: object) -> object:
        if len(p.y) < 590:  # the overlap population and subgroups (smaller samples)
            raise ValueError("synthetic failure at row 12345")
        return real_fit(p, *args, **kwargs)  # type: ignore[arg-type]

    def placebo_fails(*_: object) -> None:
        raise RuntimeError("placebo broke with 7 rows")

    monkeypatch.setattr(m, "fit_irm", fit_or_fail)
    monkeypatch.setattr(m, "placebo", placebo_fails)
    monkeypatch.setattr(m, "secondaries", lambda *_: (_ for _ in ()).throw(KeyError("s1 99")))
    written: list[dict] = []

    def checkpoint(r: object) -> None:
        m.write_json(r, tmp_path / "results.json")  # type: ignore[arg-type]
        written.append(dict(r))  # type: ignore[call-overload]

    results = m.run(
        frame, settings, with_r=False, work=tmp_path, log=lambda _: None, checkpoint=checkpoint
    )
    assert results["status"] == "complete_with_errors"
    failed = results["failed_steps"]
    assert {"refutations.placebo", "secondaries", "overlap_population"} <= set(failed)
    assert all(f.startswith("x1_subgroups.") for f in failed if f.startswith("x1"))
    assert results["refutations"]["placebo"] == {
        "error": "RuntimeError",
        "message": "placebo broke with # rows",
    }
    assert results["secondaries"]["error"] == "KeyError"
    assert (
        "#" in results["secondaries"]["message"] and "99" not in results["secondaries"]["message"]
    )
    assert "coef" in results["robustness"]["no_head_education"]
    assert all(v.get("error") == "ValueError" for v in results["x1_subgroups"].values())
    assert any("primary" in w and "secondaries" not in w for w in written)
    assert (tmp_path / "results.json").is_file()


def test_warnings_are_recorded_not_suppressed(
    fitted: tuple[m.Prepared, m.Estimate, object],
) -> None:
    """R4: a warning raised while fitting is counted by category and template."""
    p, _, _ = fitted
    m.WARNINGS.counts.clear()
    tiny = m.Settings(n_rep=1, families=("logistic",))
    original = m.make_learner

    def unconverged(family: str, kind: str, layout: m.Layout, *args: object) -> object:
        learner = original(family, kind, layout, *args)  # type: ignore[arg-type]
        if kind == "classifier":
            learner.set_params(model__max_iter=1)
        return learner

    import unittest.mock

    with unittest.mock.patch.object(m, "make_learner", unconverged):
        m.fit_irm(p, ("logistic", "logistic"), tiny)
    counts = m.WARNINGS.as_dict()
    assert any(k.startswith("ConvergenceWarning: ") for k in counts), counts
    assert all(not any(ch.isdigit() for ch in k) for k in counts)
    m.WARNINGS.counts.clear()


def test_message_template_removes_numbers() -> None:
    assert m.message_template("value 0.5 at  row 12\nand 1e-3") == "value # at row # and #"
    assert len(m.message_template("x" * 500)) == 200


def _r_with(packages: tuple[str, ...]) -> None:
    import shutil
    import subprocess

    from curbcut_ingest import aggregate

    try:
        found = aggregate.rscript()
    except FileNotFoundError:
        pytest.skip("R is not installed")
    if not (Path(found).exists() or shutil.which(found)):
        pytest.skip("R is not installed")
    names = ", ".join(f'"{p}"' for p in packages)
    check = (
        f"ok <- all(vapply(c({names}), requireNamespace, logical(1), quietly = TRUE)); "
        "quit(status = if (ok) 0 else 3)"
    )
    if subprocess.run([found, "-e", check], cwd=c.ROOT, capture_output=True).returncode == 3:
        pytest.skip(f"R packages {names} are not installed (renv::restore)")


def test_r_benchmark_on_synthetic_data(small: pd.DataFrame, tmp_path: Path) -> None:
    """5.2 and 5.3: survey LPM and sensemakr run; both are weighted least squares with the
    same covariates and proportional weights, so their point estimates agree."""
    _r_with(("survey", "sensemakr", "nanoparquet", "jsonlite"))
    p = m.prepare(small, "poor", "exposed_primary", m.COVARIATE_SETS["primary"])
    out = m.r_benchmark(p, tmp_path)
    lpm, sens = out["survey_lpm"], out["sensemakr"]
    assert lpm["ci_low"] <= lpm["estimate"] <= lpm["ci_high"]
    assert sens["estimate"] == pytest.approx(lpm["estimate"], rel=1e-8)
    assert sens["benchmark"] == "head_education" and sens["benchmark_terms"] >= 1
    assert len(sens["bounds"]) == 3
