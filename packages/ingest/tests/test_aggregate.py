"""Aggregation orchestration and the R estimator, on INVENTED person rows only."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from curbcut_ingest import aggregate, disclosure
from curbcut_ingest.restricted import common as c

NA = pd.NA


def _people(n: int = 400, seed: int = 7) -> pd.DataFrame:
    """Invented WG-style person rows across two states and four PSUs per stratum."""
    rng = np.random.default_rng(seed)
    frame = pd.DataFrame(
        {
            "source": "test",
            "person_id": [f"p{i}" for i in range(n)],
            "state": np.where(np.arange(n) % 2 == 0, "Kano", "Lagos"),
            "state_code": np.where(np.arange(n) % 2 == 0, "NG-KN", "NG-LA"),
            "zone": np.where(np.arange(n) % 2 == 0, "North West", "South West"),
            "sector": "urban",
            "sex": np.where(np.arange(n) % 3 == 0, "female", "male"),
            "age": rng.integers(5, 80, n),
            "weight": rng.uniform(0.5, 2.0, n),
            "stratum": np.where(np.arange(n) % 2 == 0, "s1", "s2"),
            "psu": [f"psu{i % 8}" for i in range(n)],
        }
    )
    frame["age_group"] = c.age_group(frame["age"])
    frame["age_band"] = c.age_band(frame["age"])
    for domain in c.WG_DOMAINS:
        frame[domain] = pd.array(rng.choice([1, 1, 1, 1, 2, 3, 4], n), dtype="Int8")
    frame.loc[0, "seeing"] = NA
    frame["disability3"] = c.disability3(frame[list(c.WG_DOMAINS)])
    return frame


def test_wg_indicators() -> None:
    frame = _people(20)
    ind = aggregate.wg_indicators(frame, levels=True)
    assert "disability3" in ind
    assert "seeing_level_4" in ind
    seeing = frame["seeing"]
    assert ind["seeing_3plus"].isna().tolist() == seeing.isna().tolist()
    assert (ind["seeing_3plus"].dropna() == (seeing.dropna() >= 3).astype(int)).all()


def test_mpi_indicators_never_disability3() -> None:
    frame = pd.DataFrame(
        {
            "mpi_seeing_screener": pd.array([1, 0, NA], dtype="Int8"),
            "mpi_hearing_screener": pd.array([0, 0, 0], dtype="Int8"),
            "mpi_walking_screener": pd.array([0, 1, 0], dtype="Int8"),
            "mpi_selfcare": pd.array([1, 3, NA], dtype="Int8"),
            "mpi_cognition": pd.array([4, 1, 1], dtype="Int8"),
            "mpi_communication": pd.array([1, 1, 2], dtype="Int8"),
            "mpi_upper_body": pd.array([2, 2, 2], dtype="Int8"),
        }
    )
    ind = aggregate.mpi_indicators(frame)
    assert "disability3" not in ind
    assert ind["mpi_screener_seeing_any"].tolist() == [1, 0, NA]
    assert ind["mpi_selfcare_3plus"].tolist() == [0, 1, NA]
    assert ind["mpi_cognition_3plus"].tolist() == [1, 0, 0]


def test_jobs_shape() -> None:
    frame = _people(20)
    dhs = aggregate.dhs_jobs(frame)
    assert [j.filename for j in dhs] == ["dhs2024_state.csv", "dhs2024_national.csv"]
    assert {g.labels["age_group"] for g in dhs[0].groups} == {"18+", "5-17"}
    ghs = aggregate.ghs_jobs("ghs_w4")(frame)[0]
    # GHS never goes below zone level.
    assert {g.labels["geography_level"] for g in ghs.groups} == {"national", "zone"}
    assert all(g.by != "state_code" for g in ghs.groups)
    assert not aggregate.DATASETS["mpi2021"].held  # released 2026-10-24
    assert not aggregate.DATASETS["dhs2024"].held


def test_analysis_frame() -> None:
    frame = _people(10)
    out = aggregate.analysis_frame(frame, aggregate.wg_indicators(frame))
    assert set(out["national"]) == {"NG"}
    assert out["disability3"].dtype == "float64"
    assert "person_id" not in out.columns


def _fake_r(raw: pd.DataFrame):
    def run(cmd, **kwargs):
        spec = json.loads(Path(cmd[-1]).read_text(encoding="utf-8"))
        assert Path(spec["input"]).exists()
        raw.to_csv(spec["output"], index=False)
        return subprocess.CompletedProcess(cmd, 0)

    return run


def test_main_with_fake_r(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    derived = tmp_path / "derived"
    c.write_parquet(_people(40), "ghs_w4", derived)
    raw = pd.DataFrame(
        [
            {"measure": "disability3", "geography_level": "national", "geography": "NG",
             "age_group": "18+", "sex": "all", "estimate": 0.1, "se": 0.01, "ci_low": 0.08,
             "ci_high": 0.12, "n_unweighted": 300, "n_events": 30, "n_effective": 250.0,
             "df": 6},
            {"measure": "disability3", "geography_level": "zone", "geography": "North West",
             "age_group": "18+", "sex": "all", "estimate": 0.2, "se": 0.05, "ci_low": 0.1,
             "ci_high": 0.3, "n_unweighted": 12, "n_events": 2, "n_effective": 10.0,
             "df": 3},
        ]
    )  # fmt: skip
    monkeypatch.setattr("curbcut_ingest.aggregate.subprocess.run", _fake_r(raw))
    monkeypatch.setattr(aggregate, "rscript", lambda: "Rscript")
    out_root = tmp_path / "public"
    code = aggregate.main(
        ["--sources", "ghs_w4", "--derived", str(derived), "--out-root", str(out_root)]
    )
    assert code == 0
    published = pd.read_csv(out_root / "ghs_w4_national_zone.csv")
    assert published["suppressed"].tolist() == [False, True]
    assert published["precision_flag"].tolist() == ["review", "suppressed"]


def test_rscript_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RSCRIPT", "/opt/R/bin/Rscript")
    assert aggregate.rscript() == "/opt/R/bin/Rscript"


def _find_rscript() -> str | None:
    """The Rscript that aggregate would use, if it really exists on this machine."""
    try:
        found = aggregate.rscript()
    except FileNotFoundError:
        return None
    return found if Path(found).exists() or shutil.which(found) else None


R_PACKAGES_CHECK = (
    'ok <- all(vapply(c("survey", "nanoparquet", "jsonlite"), requireNamespace, logical(1), '
    "quietly = TRUE)); quit(status = if (ok) 0 else 3)"
)


@pytest.fixture(scope="module")
def r_ready() -> str:
    """Rscript with survey, nanoparquet and jsonlite; skip only when they are truly absent."""
    found = _find_rscript()
    if found is None:
        pytest.skip("R is not installed")
    check = subprocess.run([found, "-e", R_PACKAGES_CHECK], cwd=c.ROOT, capture_output=True)
    if check.returncode == 3:
        pytest.skip("R packages survey / nanoparquet / jsonlite are not installed (renv::restore)")
    assert check.returncode == 0, "Rscript failed for a reason other than missing packages"
    return found


def test_estimate_r_against_hand_calculation(r_ready: str, tmp_path: Path) -> None:
    """Run the real R script on invented rows and check the point estimates by hand."""
    frame = _people(400)
    job = aggregate.dhs_jobs(frame)[0]
    raw = aggregate.run_job("dhs2024", frame, job, tmp_path)  # an R failure fails the test
    cell = raw[(raw.measure == "disability3") & (raw.geography == "NG-KN")]
    cell = cell[cell.age_group == "18+"].iloc[0]
    sub = frame[(frame.state_code == "NG-KN") & (frame.age_group == "18+")]
    sub = sub[sub.disability3.notna()]
    expected = np.average(sub.disability3.astype(float), weights=sub.weight)
    assert cell.estimate == pytest.approx(expected, rel=1e-9)
    assert cell.n_unweighted == len(sub)
    assert cell.ci_low <= cell.estimate <= cell.ci_high
    assert cell.df == 4 - 1  # four PSUs in one stratum
    public = disclosure.gate(raw, aggregate.DATASETS["dhs2024"])
    assert public["precision_flag"].notna().all()


def _clustered_people(seed: int = 11) -> pd.DataFrame:
    """Invented adults: strata s1 and s2 with 4 PSUs each, s3 with a single PSU, and an
    outcome that depends on the PSU (so the design effect is above 1)."""
    rng = np.random.default_rng(seed)
    psus = [("s1", f"a{i}") for i in range(4)] + [("s2", f"b{i}") for i in range(4)]
    psus.append(("s3", "c0"))
    rows = []
    for k, (stratum, psu) in enumerate(psus):
        rate = 0.05 + 0.04 * (k % 4)
        for _ in range(60):
            rows.append(
                {"stratum": stratum, "psu": psu, "weight": float(rng.uniform(0.5, 2.0)),
                 "disability3": int(rng.random() < rate)}
            )  # fmt: skip
    frame = pd.DataFrame(rows)
    frame["state_code"] = "NG-KN"
    frame["zone"] = "North West"
    frame["sex"] = "male"
    frame["age_group"] = "18+"
    return frame


SVYCIPROP = """
options(survey.lonely.psu = "adjust")
args <- commandArgs(trailingOnly = TRUE)
d <- as.data.frame(nanoparquet::read_parquet(args[1]))
des <- survey::svydesign(ids = ~psu, strata = ~stratum, weights = ~weight, data = d,
                         nest = TRUE)
ci <- survey::svyciprop(~disability3, des, method = "beta")
write.csv(data.frame(lo = confint(ci)[1], hi = confint(ci)[2]), args[2], row.names = FALSE)
"""


def test_korn_graubard_matches_svyciprop_beta(r_ready: str, tmp_path: Path) -> None:
    """A national cell with effective n < n and a single-PSU stratum: our interval must equal
    survey::svyciprop(method = "beta"), and the lonely PSU must not break the variance."""
    frame = _clustered_people()
    job = aggregate.Job(
        "check.csv",
        [aggregate._group("national", "national", "18+", ["disability3"])],
        lambda f: {"disability3": f["disability3"]},
    )
    raw = aggregate.run_job("dhs2024", frame, job, tmp_path)
    cell = raw.iloc[0]
    assert cell.n_unweighted == len(frame)
    assert cell.n_effective < cell.n_unweighted  # clustering: design effect above 1
    assert cell.df == 9 - 3  # nine PSUs, three strata (one of them lonely)
    assert np.isfinite(cell.se) and cell.se > 0

    script = tmp_path / "svyciprop.R"
    script.write_text(SVYCIPROP, encoding="utf-8")
    out = tmp_path / "svyciprop.csv"
    data = tmp_path / "check.input.parquet"
    subprocess.run([r_ready, str(script), str(data), str(out)], cwd=c.ROOT, check=True)
    reference = pd.read_csv(out).iloc[0]
    assert cell.ci_low == pytest.approx(reference.lo, rel=1e-8)
    assert cell.ci_high == pytest.approx(reference.hi, rel=1e-8)


def test_run_r_withholds_r_messages(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def fake(cmd, **kwargs):
        return subprocess.CompletedProcess(
            cmd, 1, stdout="estimate.R: 10 rows\nvalue 12345\n", stderr="Error: secret 678\n"
        )

    monkeypatch.setattr("curbcut_ingest.aggregate.subprocess.run", fake)
    with pytest.raises(subprocess.CalledProcessError) as info:
        aggregate.run_r(["Rscript", "estimate.R", "spec.json"])
    out = capsys.readouterr().out
    assert "estimate.R: 10 rows" in out
    assert "12345" not in out and "678" not in out
    assert "2 other output lines withheld" in out
    assert info.value.output is None and info.value.stderr is None
