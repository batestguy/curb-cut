"""P5 exploratory E1 (pre-registration section 8) on SYNTHETIC data only.

Every row is invented (:func:`p5_ghs.synthetic_panel` or written by hand); nothing reads
``data/restricted/``.
"""

from __future__ import annotations

import math
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from curbcut_ingest import aggregate
from curbcut_ingest.restricted import common as c
from curbcut_ingest.restricted import p5_ghs as g
from curbcut_ingest.restricted import p5_mpi as m
from scipy import stats


def test_any_work_harmonisation() -> None:
    items = pd.DataFrame({"a": [1, 2, 2, None, 2], "b": [2, 2, 1, 2, None]})
    assert g.any_work(items).tolist() == [1, 0, 1, pd.NA, pd.NA]


def test_severe_any_needs_all_six_domains_for_a_zero() -> None:
    rows = pd.DataFrame(
        [[1, 1, 1, 1, 1, 1], [1, 1, 3, 1, 1, None], [1, 2, 2, 2, 1, None], [1, 1, 1, 1, 1, 9]],
        columns=list(c.WG_DOMAINS),
    )
    assert g.severe_any(rows).tolist() == [0, 1, pd.NA, pd.NA]


def _w4_row(hhid: int, indiv: int, age: int, **domains: float) -> dict:
    base: dict[str, float] = {f"w4_{d}": 1 for d in c.WG_DOMAINS}
    base.update({f"w4_{k}": v for k, v in domains.items()})
    person = {"hhid": hhid, "indiv": indiv, "age": age, "sex": "female", "zone": "North West"}
    household = {"sector": "rural", "cluster": hhid, "weight_w4": 100.0, "consumption_w4": 1000.0}
    return {**person, **household, "work_w4": 1.0, **base}


def _w5_row(hhid: int, indiv: int, **domains: float) -> dict:
    base: dict[str, float] = {f"w5_{d}": 1 for d in c.WG_DOMAINS}
    base.update({f"w5_{k}": v for k, v in domains.items()})
    return {
        "hhid": hhid,
        "indiv": indiv,
        "work_w5": 0.0,
        "consumption_w5": 1500.0,
        "weight_long": 120.0,
        **base,
    }


def test_build_panel_linkage_sample_and_changes() -> None:
    w4 = pd.DataFrame([
        _w4_row(1, 1, 40),
        _w4_row(1, 2, 10),  # under 15: not in the panel
        _w4_row(2, 1, 50, walking=3),  # severe in W4: not at risk of onset
        _w4_row(3, 1, 30),  # not found in W5 (attrition)
        _w4_row(4, 1, 25),
    ])  # fmt: skip
    w5 = pd.DataFrame([_w5_row(1, 1, seeing=4), _w5_row(2, 1), _w5_row(4, 1), _w5_row(9, 1)])
    panel = g.build_panel(w4, w5)
    assert panel.linkage["w4_people_15plus"] == "<30"  # 4 people, masked
    assert panel.linkage["linkage_rate"] == pytest.approx(3 / 4)
    f = panel.frame
    assert len(f) == 2  # people (1,1) and (4,1)
    assert f["onset"].tolist() == [1.0, 0.0]
    assert f["dlog_consumption"].tolist() == pytest.approx([math.log(1.5)] * 2)
    assert f["dwork"].tolist() == [-1.0, -1.0]
    assert f["age_band"].tolist() == ["30-44", "15-29"]
    assert f["weight"].tolist() == [120.0, 120.0]
    names = [row["characteristic"] for row in panel.attrition]
    assert {"age", "female", "urban", "severe_w4"} <= set(names)


def test_icc_against_hand_values() -> None:
    # Two clusters, perfectly separated: ICC = 1. No between-cluster variation: ICC = 0.
    assert g.icc_anova(np.array([0.0, 0.0, 1.0, 1.0]), np.array([1, 1, 2, 2])) == pytest.approx(1.0)
    assert g.icc_anova(np.array([0.0, 1.0, 0.0, 1.0]), np.array([1, 1, 2, 2])) == 0.0
    # Balanced one-way ANOVA by hand: groups (1, 2, 3) and (4, 5, 9).
    y = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 9.0])
    grp = np.array([1, 1, 1, 2, 2, 2])
    msb = 3 * ((2 - 4) ** 2 + (6 - 4) ** 2) / 1  # 24
    msw = ((1 + 0 + 1) + (4 + 1 + 9)) / 4  # 4
    assert g.icc_anova(y, grp) == pytest.approx((msb - msw) / (msb + 2 * msw))


def test_mde_against_hand_computation() -> None:
    change = np.array([0.0, 0.0, 1.0, 1.0])
    onset = np.array([1.0, 0.0, 1.0, 0.0])
    weights = np.array([1.0, 1.0, 2.0, 2.0])
    clusters = np.array([1, 1, 2, 2])
    out = g.mde(change, onset, weights, clusters)
    z = stats.norm.ppf(0.975) + stats.norm.ppf(0.80)  # 2.8016
    deff_kish = 4 * (1 + 1 + 4 + 4) / 6**2  # 1.111
    deff_cluster = 1 + (2 - 1) * 1.0  # ICC 1, clusters of 2
    expected_sd_units = z * math.sqrt(deff_kish * deff_cluster / (4 * 0.5 * 0.5))
    assert out["deff_kish"] == pytest.approx(deff_kish)
    assert out["deff_cluster"] == pytest.approx(deff_cluster)
    assert out["mde_sd"] == pytest.approx(expected_sd_units)
    assert out["mde"] == pytest.approx(expected_sd_units * np.std(change, ddof=1))
    assert out["run"] is False  # far above 0.5 SD
    # Missing changes are dropped before anything is counted.
    with_missing = g.mde(
        np.append(change, np.nan),
        np.append(onset, 1.0),
        np.append(weights, 1.0),
        np.append(clusters, 3),
    )
    assert with_missing["n"] == 4 and with_missing["mde_sd"] == pytest.approx(expected_sd_units)


def test_mde_rule_runs_with_enough_onset_cases() -> None:
    rng = np.random.default_rng(0)
    n = 4000
    out = g.mde(
        rng.normal(size=n), (rng.random(n) < 0.2).astype(float), np.ones(n), np.arange(n) // 10
    )
    # Hand: deff ~ 1, MDE ~ 2.8016 / sqrt(4000 * 0.2 * 0.8) = 0.11 SD.
    assert out["mde_sd"] == pytest.approx(2.8016 / math.sqrt(n * 0.2 * 0.8), rel=0.1)
    assert out["run"] is True


@pytest.fixture(scope="module")
def panel() -> g.Panel:
    w4, w5 = g.synthetic_panel()
    return g.build_panel(w4, w5)


def test_change_model_recovers_synthetic_effects(panel: g.Panel) -> None:
    consumption = g.change_model(panel.frame, "dlog_consumption")
    assert consumption["ci_low"] <= -0.15 <= consumption["ci_high"]
    work = g.change_model(panel.frame, "dwork")
    assert work["ci_low"] <= -0.10 <= work["ci_high"]


def test_run_e1_without_r(panel: g.Panel) -> None:
    out = g.run_e1(panel, with_r=False)
    assert set(out["outcomes"]) == set(g.OUTCOMES)
    for entry in out["outcomes"].values():
        assert ("model" in entry) == entry["power"]["run"]
        assert ("not_run" in entry) != entry["power"]["run"]


def _r_with_fixest() -> str:
    try:
        found = aggregate.rscript()
    except FileNotFoundError:
        pytest.skip("R is not installed")
    if not (Path(found).exists() or shutil.which(found)):
        pytest.skip("R is not installed")
    check = (
        'ok <- all(vapply(c("fixest", "nanoparquet", "jsonlite"), requireNamespace, '
        "logical(1), quietly = TRUE)); quit(status = if (ok) 0 else 3)"
    )
    result = subprocess.run([found, "-e", check], cwd=c.ROOT, capture_output=True)
    if result.returncode == 3:
        pytest.skip("R package fixest is not installed (renv::restore)")
    return found


def test_r_fixest_matches_pyfixest(panel: g.Panel, tmp_path: Path) -> None:
    _r_with_fixest()
    py = g.change_model(panel.frame, "dlog_consumption")
    r = g.r_change_model(panel.frame, "dlog_consumption", tmp_path)
    assert r["estimate"] == pytest.approx(py["estimate"], rel=1e-6)
    assert r["se"] == pytest.approx(py["se"], rel=1e-3)
    assert r["n"] == py["n"]


def test_real_mode_refused_without_registration(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    path = tmp_path / "prereg.md"
    path.write_text("## 11. Registration record\n\nTo be filled.\n", encoding="utf-8")
    monkeypatch.setattr(g, "require_registration", lambda: m.require_registration(path))

    def boom() -> None:
        raise AssertionError("real files must not be read")

    monkeypatch.setattr(g, "load_real", boom)
    monkeypatch.setattr(c, "RESTRICTED", tmp_path)
    assert g.main(["--real", "--out-dir", str(tmp_path / "out")]) == 1
    assert not (tmp_path / "out").exists()


def test_load_real_is_guarded_too(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Defence in depth: load_real refuses by itself, before any file is opened."""
    path = tmp_path / "prereg.md"
    path.write_text("## 11. Registration record\n\nTo be filled.\n", encoding="utf-8")
    monkeypatch.setattr(g, "require_registration", lambda: m.require_registration(path))

    def boom(*_: object, **__: object) -> None:
        raise AssertionError("real files must not be read")

    monkeypatch.setattr(c, "read_dta", boom)
    with pytest.raises(m.RegistrationError):
        g.load_real()


def test_work_categories_match_across_waves() -> None:
    """D5: the same three categories in both waves; W5's helping items are not used."""
    assert set(g.W4_WORK) == set(g.W5_WORK) == {"wage", "farm_own", "nonfarm_own"}
    assert g.W5_WORK == {"wage": "s4aq4", "farm_own": "s4aq10", "nonfarm_own": "s4aq6"}
    assert not {"s4aq8", "s4aq11"} & set(g.W5_WORK.values())


def test_out_dir_must_be_in_the_restricted_zone(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(c, "RESTRICTED", tmp_path / "restricted")
    assert g.main(["--no-r", "--out-dir", str(tmp_path / "public")]) == 2
    assert not (tmp_path / "public").exists()


def test_main_synthetic(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(c, "RESTRICTED", tmp_path)
    assert g.main(["--no-r", "--out-dir", str(tmp_path)]) == 0
    assert (tmp_path / "ghs_results.json").is_file()
