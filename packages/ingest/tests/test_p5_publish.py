"""The P5 publisher and the model-estimate gate, on invented results with the real shape.

No real result is used: :func:`fake_results` and :func:`fake_ghs` make files with the keys
``p5_mpi`` and ``p5_ghs`` write, and invented numbers.
"""

from __future__ import annotations

import copy
import csv
import json
import math
from pathlib import Path
from typing import Any

import pandas as pd
import pytest
from curbcut_ingest import disclosure
from curbcut_ingest.restricted import p5_publish as pub

PREREG_TEXT = """# Pre-registration

## 11. Registration record

- **Code freeze:** tag `p5-freeze`, commit `22b8acee10b304f25201627d5cf4da47c2544a19`.
- **SHA-256 at the freeze:**
  - `docs/preregistration.md`: `65d0a4b2a3047e499f497aa8b59e5917ad74612c63fc8b2c66bd25af69e82955`
- **OSF registration:** https://osf.io/abcde/ , registered 2026-11-01 05:49:21 UTC (OSF).
"""
ZONES = pub.ZONES


def est(coef: float = 0.1, n: int = 1000, exposed: str = "100", **over: Any) -> dict[str, Any]:
    out = {
        "coef": coef,
        "se": 0.02,
        "ci_low": coef - 0.04,
        "ci_high": coef + 0.04,
        "pval": 0.001,
        "n": n,
        "n_exposed": exposed,
        "all_coef": [coef] * 5,
        "mu0": 0.6,
        "learners": ["boosting", "logistic"],
        "n_rep": 5,
    }
    out.update(over)
    return out


def selection() -> dict[str, Any]:
    cand = {
        k: {"mean": 0.5 + i / 100, "se": 0.01, "folds": [0.5] * 5}
        for i, k in enumerate(("logistic", "forest", "boosting"))
    }
    return {
        "metric": "log loss",
        "outcome": {"candidates": cand, "lowest": "logistic", "chosen": "logistic"},
        "propensity": {"candidates": cand, "lowest": "logistic", "chosen": "logistic"},
    }


def bounds(lo: float, hi: float) -> dict[str, Any]:
    return {
        "theta": {"lower": lo, "upper": hi},
        "se": {"lower": 0.02, "upper": 0.02},
        "ci": {"lower": lo - 0.04, "upper": hi + 0.04},
        "rv": 0.3,
        "rva": 0.2,
        "input": {"cf_y": 0.1, "cf_d": 0.01, "rho": 0.05, "level": 0.95},
    }


def fake_results() -> dict[str, Any]:
    secondaries: dict[str, Any] = {
        name: {"estimate": est(0.05), "selection": selection()} for name in pub.SECONDARIES
    }
    for name in ("s1_score", "s2_broad", "s3_head"):
        secondaries[name]["holm_p"] = 0.003
        secondaries[name]["supported"] = True
    benchmarks = {
        name: {
            "dropped": [name],
            "strengths": {"cf_y": 0.1, "cf_d": 0.01, "rho": 0.05, "delta_theta": 0.01},
            "bounds": bounds(0.09, 0.11),
        }
        for name in ("head_education", "place", "sector")
    }
    sensemakr_bounds = [
        {
            "label": f"{k}x head_education",
            "r2dz_x": 0.001 * k,
            "r2yz_dx": 0.06 * k,
            "adjusted_estimate": 0.08 - 0.02 * k,
            "adjusted_lower_ci": 0.05 - 0.02 * k,
            "adjusted_upper_ci": 0.11 - 0.02 * k,
        }
        for k in (1, 2, 3)
    ]
    return {
        "status": "complete",
        "failed_steps": [],
        "table7": {
            "values": {"exposed": 72.0, "unexposed": 61.8, "gap": 10.2},
            "published": {"exposed": 71.4, "unexposed": 61.8, "gap": 9.6},
            "tolerance": 2.0,
            "pass": {"exposed": True, "unexposed": True, "gap": True},
            "all_pass": True,
        },
        "weights": {"n": 1000, "kish_effective_n": 600.5, "max_weight_share": 0.001},
        "learner_selection": {"folds": 5, **selection()},
        "primary": {**est(0.1), "wording": "difference"},
        "evalue": {
            "rr": 1.17,
            "rr_ci_low": 1.1,
            "rr_ci_high": 1.25,
            "evalue": 1.6,
            "evalue_ci": 1.4,
        },
        "overlap": {
            "clipped_share": {"weighted": 0.6, "unweighted": 0.62},
            "outside_overlap_population": {
                "households": "600",
                "weighted_share": 0.59,
                "unweighted_share": 0.6,
            },
            "range": [0.01, 0.99],
            "quantiles_by_exposure": {
                group: {
                    "households": count,
                    **{
                        k: v
                        for k, v in zip(
                            ("q01", "q05", "q25", "q50", "q75", "q95", "q99"),
                            (0.001, 0.003, 0.01, 0.02, 0.05, 0.1, 0.2),
                            strict=True,
                        )
                    },
                }
                for group, count in (("exposed", "100"), ("unexposed", "900"))
            },
        },
        "overlap_population": est(0.08, n=400, exposed="80"),
        "sensitivity": {"default": bounds(-0.07, 0.3), "benchmarks": benchmarks},
        "r_benchmark": {
            "survey_lpm": {
                "estimate": 0.08,
                "se": 0.02,
                "ci_low": 0.04,
                "ci_high": 0.12,
                "df": 300,
            },
            "sensemakr": {
                "estimate": 0.08,
                "se": 0.016,
                "partial_r2_yd_x": 0.0005,
                "rv_q": 0.02,
                "rv_qa": 0.013,
                "bounds": sensemakr_bounds,
            },
            "versions": {"survey": "4.5", "sensemakr": "0.1.6", "r": "4.5.2"},
        },
        "refutations": {
            "placebo": {
                "n": 100,
                "mean": 0.001,
                "sd": 0.02,
                "share_ci_excluding_0": 0.05,
                "empirical_p_real_estimate": 0.0099,
                "coefs": [0.0] * 100,
            },
            "random_common_cause": {
                "moved": 0.003,
                "allowed": 0.02,
                "seed_range": 0.02,
                "pass": True,
                "reference": 0.12,
                "with_random_common_cause": 0.117,
                "seed_estimates": [0.12] * 5,
            },
            "leave_one_zone_out": {z: est(0.1, n=800, exposed="90") for z in ZONES},
        },
        "robustness": {name: est(0.11) for name in pub.ROBUSTNESS},
        "secondaries": secondaries,
        "x1_subgroups": {
            "sector=rural": est(0.07, n=700, exposed="70"),
            "sector=urban": est(0.2, n=300, exposed="30"),
            **{f"zone={z}": est(0.1, n=150, exposed="40") for z in ZONES},
        },
        "sample": {
            "households_in_sample": 1010,
            "missing_poor": {"households": "<30", "weighted_share_people": 0.01},
            "missing_exposure_primary": {"households": "40", "weighted_share_people": 0.002},
        },
    }


def outcome(estimate: float, run: bool = True) -> dict[str, Any]:
    model = {"estimate": estimate, "se": 0.04, "ci_low": estimate - 0.08}
    model.update({"ci_high": estimate + 0.08, "n": 900})
    out: dict[str, Any] = {
        "power": {
            "n": 900,
            "onset_cases": 40,
            "onset_share": 0.044,
            "sd_change": 0.5,
            "deff_kish": 2.0,
            "icc": 0.1,
            "mean_cluster_size": 20.0,
            "deff_cluster": 2.9,
            "deff": 5.8,
            "mde_sd": 0.45,
            "mde": 0.22,
            "run": run,
        }
    }
    if run:
        out["model"] = model
        out["r_check"] = {**model, "fixest": "0.14.2"}
    return out


def fake_ghs() -> dict[str, Any]:
    return {
        "linkage": {
            "w4_people_15plus": "1,200",
            "found_in_w5": "1,000",
            "linkage_rate": 0.83,
            "found_with_w5_answers": "950",
            "analysis_sample": "900",
            "onset_cases": "40",
        },
        "attrition": [
            {
                "characteristic": "age",
                "stayers": 37.0,
                "attriters": 32.0,
                "standardised_difference": 0.3,
            },
            *(
                {
                    "characteristic": name,
                    "stayers": 0.5,
                    "attriters": 0.4,
                    "standardised_difference": 0.1,
                }
                for name in ("female", "urban", "severe_w4")
            ),
            {
                "characteristic": "zone=1. North Central",
                "stayers": 0.17,
                "attriters": 0.14,
                "standardised_difference": 0.09,
            },
        ],
        "outcomes": {"dlog_consumption": outcome(0.03), "dwork": outcome(-0.2)},
        "mode": "real",
    }


MANIFEST = {
    "mode": "real",
    "git": {"commit": "a" * 40, "dirty": False},
    "created": "2026-11-01T09:28:07+00:00",
}


def _read(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def test_publish_all_writes_four_gated_files_and_manifest(tmp_path: Path) -> None:
    entries = pub.publish_all(fake_results(), fake_ghs(), MANIFEST, PREREG_TEXT, tmp_path)
    assert set(entries) == set(pub.FILES)
    estimates = {r["estimate_id"]: r for r in _read(tmp_path / "p5_mpi_estimates.csv")}
    for needed in ("primary", "overlap_population", "survey_lpm", "s2_broad", "s3_head"):
        assert estimates[needed]["group"] == "headline"
    assert estimates["s4_health"]["group"] == "dimension"
    assert estimates["sensemakr_3x"]["estimate"] == "0.02"
    assert estimates["primary"]["n_unexposed"] == "900"
    assert estimates["lozo_south_west"]["label"] == "Without the South West zone"
    assert estimates["x1_sector_rural"]["label"] == "Rural areas"
    assert estimates["x1_zone_north_east"]["label"] == "North East zone"
    assert estimates["s1_score"]["supported"] == "True"
    # The 100 placebo estimates and the fold losses never leave.
    summary = _read(tmp_path / "p5_mpi_summary.csv")
    ids = [r["item_id"] for r in summary]
    assert not [i for i in ids if "coef" in i or ("fold" in i and i != "folds")]
    assert len([i for i in ids if i.endswith("_mean_loss")]) == 6
    items = {r["item_id"]: r for r in summary}
    assert items["osf_url"]["value_text"] == "https://osf.io/abcde/"
    assert items["registered_utc"]["value_text"] == "2026-11-01 05:49:21 UTC"
    assert items["freeze_commit"]["value_text"].startswith("22b8acee")
    # A masked count ("<30") is suppressed in the summary.
    assert items["missing_poor_households"]["suppressed"] == "True"
    assert items["missing_poor_households"]["value"] == ""
    ghs = {r["estimate_id"]: r for r in _read(tmp_path / "p5_ghs_estimates.csv")}
    assert set(ghs) == {
        "ghs_dlog_consumption",
        "ghs_dlog_consumption_r",
        "ghs_dwork",
        "ghs_dwork_r",
    }
    assert ghs["ghs_dwork"]["n_exposed"] == "40"
    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    entry = manifest["files"]["p5_mpi_estimates.csv"]
    assert entry["dataset_version"] == "NGA-NBS-MPI-2021-v1.0"
    assert entry["disclosure_rule"] == disclosure.ESTIMATE_RULE
    assert entry["suppressed_cells"] == 0
    assert len(entry["sha256"]) == 64
    assert "World Bank" in manifest["files"]["p5_ghs_summary.csv"]["terms"]


def test_small_arm_is_suppressed_with_both_counts(tmp_path: Path) -> None:
    results = fake_results()
    results["x1_subgroups"]["zone=North East"] = est(0.3, n=150, exposed="<30")
    results["x1_subgroups"]["zone=South West"] = est(0.3, n=40, exposed="35")  # 5 unexposed
    pub.publish_all(results, fake_ghs(), MANIFEST, PREREG_TEXT, tmp_path)
    rows = {r["estimate_id"]: r for r in _read(tmp_path / "p5_mpi_estimates.csv")}
    for eid in ("x1_zone_north_east", "x1_zone_south_west"):
        row = rows[eid]
        assert row["suppressed"] == "True"
        assert row["estimate"] == row["ci_low"] == row["ci_high"] == row["mu0"] == ""
        assert row["n_exposed"] == row["n_unexposed"] == ""
    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["files"]["p5_mpi_estimates.csv"]["suppressed_cells"] == 2


def test_ghs_outcome_not_run_is_left_out() -> None:
    ghs = fake_ghs()
    ghs["outcomes"]["dlog_consumption"] = outcome(0.0, run=False)
    frame = pub.ghs_estimates(ghs)
    assert list(frame["estimate_id"]) == ["ghs_dwork", "ghs_dwork_r"]
    summary = pub.ghs_summary(ghs)
    run = summary.set_index("item_id").loc["dlog_consumption_run", "value"]
    assert run == 0.0


@pytest.mark.parametrize(
    "change",
    [
        lambda r: r.update(status="complete_with_errors"),
        lambda r: r["secondaries"]["s2_broad"].update(error="ValueError"),
        lambda r: r["primary"].update(ci_low=0.5),  # estimate outside its interval
        lambda r: r["sensitivity"]["benchmarks"]["place"].update(error="x"),
    ],
)
def test_bad_results_publish_nothing(tmp_path: Path, change: Any) -> None:
    results = copy.deepcopy(fake_results())
    change(results)
    with pytest.raises((pub.PublishError, disclosure.GateError)):
        pub.publish_all(results, fake_ghs(), MANIFEST, PREREG_TEXT, tmp_path)
    assert not list(tmp_path.iterdir())


def test_refuses_synthetic_or_dirty_runs(tmp_path: Path) -> None:
    with pytest.raises(pub.PublishError):
        pub.publish_all(fake_results(), fake_ghs(), {"mode": "synthetic"}, PREREG_TEXT, tmp_path)
    dirty = {**MANIFEST, "git": {"commit": "a", "dirty": True}}
    with pytest.raises(pub.PublishError, match="dirty"):
        pub.publish_all(fake_results(), fake_ghs(), dirty, PREREG_TEXT, tmp_path)
    ghs = {**fake_ghs(), "mode": "synthetic"}
    with pytest.raises(pub.PublishError):
        pub.publish_all(fake_results(), ghs, MANIFEST, PREREG_TEXT, tmp_path)
    assert not list(tmp_path.iterdir())


def test_registration_needs_section_11() -> None:
    with pytest.raises(pub.PublishError, match="OSF"):
        pub.registration("# Pre-registration\n\n## 11. Registration record\n\nnot yet\n")
    partial = PREREG_TEXT.replace("registered 2026", "on 2026")
    with pytest.raises(pub.PublishError, match="registered_utc"):
        pub.registration(partial)


def test_deviations_count_and_summary_line() -> None:
    log = "# Deviations\n\nNo deviations as of 2026-11-01.\n"
    assert pub.deviations_count(log) == 0
    two = log + "\n## 2026-11-02 Changed X\n\ntext\n\n## 2026-11-03 Changed Y\n"
    assert pub.deviations_count(two) == 2
    items = pub.mpi_summary(fake_results(), MANIFEST, PREREG_TEXT, two).set_index("item_id")
    assert items.loc["deviations", "value_text"] == "2"
    none = pub.mpi_summary(fake_results(), MANIFEST, PREREG_TEXT, log).set_index("item_id")
    assert none.loc["deviations", "value_text"] == "none"
    assert none.loc["quantile_exposed_q50", "value"] == 0.02
    assert none.loc["rcc_seed_min", "value"] == 0.12


def test_parse_count() -> None:
    assert disclosure.parse_count("5,269") == 5269
    assert disclosure.parse_count("<30") == 29
    assert disclosure.parse_count(12) == 12
    assert disclosure.parse_count(None) is None
    assert disclosure.parse_count(math.nan) is None
    with pytest.raises(disclosure.GateError):
        disclosure.parse_count(True)


DATASET = disclosure.Dataset("t", "v1", "Test", "Invented", "Invented", "Invented")


def _estimate(**over: Any) -> dict[str, Any]:
    row: dict[str, Any] = {c: None for c in disclosure.ESTIMATE_COLUMNS}
    row.update(
        analysis="mpi",
        group="headline",
        estimate_id="a",
        label="A",
        estimate=0.1,
        se=0.01,
        ci_low=0.08,
        ci_high=0.12,
        n=100,
        n_exposed=50,
        n_unexposed=50,
    )
    row.update(over)
    return row


def test_gate_estimates_rules() -> None:
    frame = pd.DataFrame(
        [
            _estimate(),
            _estimate(estimate_id="b", n_exposed=29, n_unexposed=71),
            _estimate(estimate_id="c", n_exposed=70, n_unexposed=30),
        ]
    )
    out = disclosure.gate_estimates(frame, DATASET).set_index("estimate_id")
    assert list(out["suppressed"]) == [False, True, False]
    assert pd.isna(out.loc["b", "estimate"])
    assert out.loc["c", "estimate"] == 0.1
    with pytest.raises(disclosure.GateError, match="share"):
        disclosure.gate_estimates(pd.DataFrame([_estimate(), _estimate()]), DATASET)
    with pytest.raises(disclosure.GateError, match="lack"):
        disclosure.gate_estimates(pd.DataFrame([{"estimate_id": "a"}]), DATASET)
    with pytest.raises(disclosure.GateError, match="present"):
        disclosure.gate_estimates(pd.DataFrame([_estimate(n_unexposed=None)]), DATASET)
    with pytest.raises(disclosure.GateError, match="interval"):
        disclosure.gate_estimates(pd.DataFrame([_estimate(ci_low=None)]), DATASET)


def _summary(**over: Any) -> dict[str, Any]:
    row = {
        "analysis": "mpi",
        "section": "s",
        "item_id": "i",
        "label": "L",
        "kind": "number",
        "value": 1.5,
        "value_text": None,
    }
    row.update(over)
    return row


def test_gate_summary_rules(tmp_path: Path) -> None:
    rows = [
        _summary(),
        _summary(item_id="c0", kind="count", value=0),
        _summary(item_id="c1", kind="count", value="12"),
        _summary(item_id="t", kind="text", value=None, value_text="hello"),
    ]
    out = disclosure.gate_summary(pd.DataFrame(rows), DATASET).set_index("item_id")
    assert list(out["suppressed"]) == [False, False, True, False]
    assert out.loc["c0", "value"] == 0.0
    assert out.loc["t", "value_text"] == "hello"
    bad = [
        [_summary(), _summary()],
        [_summary(kind="colour")],
        [_summary(kind="text", value_text=None)],
        [_summary(kind="count", value=None)],
        [_summary(value=None)],
        [{"item_id": "x"}],
    ]
    for case in bad:
        with pytest.raises(disclosure.GateError):
            disclosure.gate_summary(pd.DataFrame(case), DATASET)
    held = disclosure.Dataset("h", "v", "H", "c", "t", "d", held=True)
    with pytest.raises(disclosure.GateError, match="held"):
        disclosure.publish_summary(pd.DataFrame([_summary()]), held, "x.csv", tmp_path)


def test_main_refuses_without_results(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    results = tmp_path / "results.json"
    results.write_text(json.dumps({"status": "complete"}), encoding="utf-8")
    ghs = tmp_path / "ghs.json"
    ghs.write_text(json.dumps(fake_ghs()), encoding="utf-8")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps(MANIFEST), encoding="utf-8")
    out = tmp_path / "out"
    code = pub.main(
        [
            "--results",
            str(results),
            "--ghs-results",
            str(ghs),
            "--manifest",
            str(manifest),
            "--out-root",
            str(out),
        ]
    )
    assert code == 1
    assert "refused" in capsys.readouterr().out
    assert not out.exists()


def test_main_publishes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    prereg = tmp_path / "prereg.md"
    prereg.write_text(PREREG_TEXT, encoding="utf-8")
    monkeypatch.setattr(pub, "PREREG", prereg)
    paths = {}
    for name, data in (("r", fake_results()), ("g", fake_ghs()), ("m", MANIFEST)):
        paths[name] = tmp_path / f"{name}.json"
        paths[name].write_text(json.dumps(data), encoding="utf-8")
    out = tmp_path / "out"
    argv = ["--results", str(paths["r"]), "--ghs-results", str(paths["g"])]
    argv += ["--manifest", str(paths["m"]), "--out-root", str(out)]
    assert pub.main(argv) == 0
    assert sorted(p.name for p in out.iterdir()) == sorted([*pub.FILES.values(), "manifest.json"])
