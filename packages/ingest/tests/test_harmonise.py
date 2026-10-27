"""Harmonisers for DHS 2024, MPI 2021 and GHS W4/W5 on INVENTED person rows.

Nothing here comes from the real microdata: every row is made up to exercise one rule
(routing, don't-know handling, filters, joins). The real files are never in git or CI.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
from curbcut_ingest.restricted import common as c
from curbcut_ingest.restricted import dhs2024, ghs, mpi2021
from curbcut_ingest.states import StateLookup

pyreadstat = pytest.importorskip("pyreadstat")
NA = pd.NA
LOOKUP = StateLookup.from_seeds()
STATE_LABELS = {i + 1: name.upper() for i, name in enumerate(sorted(LOOKUP.states))}
CODE_OF = {name: i + 1 for i, name in enumerate(sorted(LOOKUP.states))}


def _write(path: Path, rows: list[dict], labels: dict[str, dict[int, str]] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame(rows).astype("float64")
    pyreadstat.write_dta(frame, str(path), variable_value_labels=labels or {})


# --- DHS 2024 -------------------------------------------------------------------------


def _dhs_row(**over: float | None) -> dict:
    row: dict[str, float | None] = {
        "hv001": 1, "hv002": 1, "hvidx": 1, "hv005": 2_000_000, "hv021": 1, "hv023": 1,
        "hv025": 1, "hv103": 1, "hv104": 2, "hv105": 30, "hv270": 3, "shstate": CODE_OF["Kano"],
        "hdis2": 1, "hdis4": 1, "hdis5": 1, "hdis6": 1, "hdis7": 1, "hdis8": 1, "hdis9": 1,
    }  # fmt: skip
    row.update(over)
    return row


DHS_ROWS = [
    _dhs_row(hvidx=1),  # no difficulty
    _dhs_row(hvidx=2, hdis7=3, hdis9=3, hv270=5, hv025=2),  # a lot of difficulty walking
    _dhs_row(hvidx=3, hdis2=8, hv270=None),  # don't know seeing; wealth missing
    _dhs_row(hvidx=4, hv103=0),  # not de facto: dropped
    _dhs_row(hvidx=5, hv105=4),  # under 5: dropped
    _dhs_row(hvidx=6, hv105=98),  # age unknown: dropped
    _dhs_row(hvidx=7, hv105=12, hdis4=4, hdis9=4, hv270=1),  # child, cannot hear, poorest
    {**_dhs_row(hvidx=8), **{f"hdis{i}": None for i in (2, 4, 5, 6, 7, 8, 9)}},  # not asked
]


def test_dhs_harmonise_rules() -> None:
    raw = pd.DataFrame(DHS_ROWS).astype("float64")
    out = dhs2024.harmonise(raw, STATE_LABELS, LOOKUP)
    assert out["person_id"].tolist() == ["dhs2024-1-1-1", "dhs2024-1-1-2", "dhs2024-1-1-3",
                                         "dhs2024-1-1-7"]  # fmt: skip
    assert out["disability3"].tolist() == [0, 1, NA, 1]
    assert out["seeing"].tolist() == [1, 1, NA, 1]
    assert out["age_group"].tolist() == ["18+", "18+", "18+", "5-17"]
    assert out["weight"].tolist() == [2.0] * 4
    assert set(out["state_code"]) == {"NG-KN"}
    assert set(out["zone"]) == {"North West"}
    assert out["wealth_quintile"].tolist() == ["middle", "highest", NA, "lowest"]
    assert out["sector"].tolist() == ["urban", "rural", "urban", "urban"]
    assert out["stratum"].iloc[0] == "dhs2024-1"
    assert list(out.columns[: len(c.COMMON_COLUMNS)]) == list(c.COMMON_COLUMNS)


def test_dhs_main_on_invented_file(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    src = tmp_path / "pr.dta"
    _write(src, DHS_ROWS, {"shstate": STATE_LABELS})
    assert dhs2024.main(["--input", str(src), "--out-dir", str(tmp_path / "derived")]) == 0
    out = pd.read_parquet(tmp_path / "derived" / "dhs2024.parquet")
    assert len(out) == 4
    log = capsys.readouterr().out
    assert "<30" in log  # every count here is small, so all are masked
    assert "disagreements: 0" in log


# --- MPI 2021 ---------------------------------------------------------------------------


def _d_row(line: int, **over: float | None) -> dict:
    row: dict[str, float | None] = {
        "hh_id": 101, "d1": line, "d2": 2, "d2a": None, "d2b": None, "d3a": 2, "d3b": None,
        "d4b": None, "d5": 2, "d6a": None, "d8": None, "d9a": 1, "d10a": 1, "d11a": 1,
        "d12a": 1, "d13a": 1, "d14a": 1,
    }  # fmt: skip
    row.update(over)
    return row


MPI_D = [
    _d_row(1),  # no screeners, no difficulty
    _d_row(2, d2=1, d2a=1, d2b=3),  # seeing: yes, wears glasses, a lot even with them
    _d_row(3, d2=1, d2a=2),  # seeing: yes, no glasses -> severity never asked
    _d_row(4, d5=1, d6a=2, d8=3),  # off route: severity without aid use -> set missing
    _d_row(5, d9a=1, d10a=4, d13a=5, d14a=2),  # communication worse = 4; upper body DK + 2
    _d_row(6, d11a=5, d12a=3),  # self-care DK -> missing; cognition 3
    _d_row(7),  # age under 5 in the roster: dropped
]
MPI_A = [{"hh_id": 101, "a1": CODE_OF["Lagos"], "a1b": 241, "a3": 1, "a4": 5555,
          "pop_wgt": 600.0, "hhsize": 6}]  # fmt: skip
MPI_B = [{"hh_id": 101, "b1": i, "b3": 1 + i % 2, "b4a": 40 - i} for i in range(1, 7)] + [
    {"hh_id": 101, "b1": 7, "b3": 1, "b4a": 3}
]


def test_mpi_routing_and_items() -> None:
    d = pd.DataFrame(MPI_D).astype("float64")
    out = mpi2021.harmonise_disability(d)
    assert out["mpi_seeing_screener"].tolist() == [0, 1, 1, 0, 0, 0, 0]
    assert out["mpi_seeing_aid"].tolist() == [NA, 1, 0, NA, NA, NA, NA]
    assert out["mpi_seeing_severity"].tolist() == [NA, 3, NA, NA, NA, NA, NA]
    assert out["mpi_walking_screener"].tolist() == [0, 0, 0, 1, 0, 0, 0]
    assert out["mpi_walking_severity"].tolist() == [NA] * 7  # off route answer removed
    assert out["mpi_communication"].tolist() == [1, 1, 1, 1, 4, 1, 1]
    assert out["mpi_upper_body"].tolist() == [1, 1, 1, 1, NA, 1, 1]
    assert out["mpi_selfcare"].tolist() == [1, 1, 1, 1, 1, NA, 1]
    assert out["mpi_cognition"].tolist() == [1, 1, 1, 1, 1, 3, 1]
    assert mpi2021.off_route_answers(d) == {"seeing": 0, "hearing": 0, "walking": 1}
    assert "disability3" not in out.columns


def test_mpi_harmonise_joins_and_design() -> None:
    a = pd.DataFrame(MPI_A).astype("float64")
    b = pd.DataFrame(MPI_B).astype("float64")
    d = pd.DataFrame(MPI_D).astype("float64")
    out = mpi2021.harmonise(a, b, d, STATE_LABELS, LOOKUP)
    assert len(out) == 6  # the under-5 is dropped
    assert out["weight"].tolist() == [100.0] * 6  # pop_wgt / hhsize
    assert set(out["stratum"]) == {f"mpi2021-{CODE_OF['Lagos']}-241-1"}  # state x a1b x a3
    assert set(out["psu"]) == {"mpi2021-5555"}
    assert set(out["state"]) == {"Lagos"}
    assert "disability3" not in out.columns


def test_mpi_main_on_invented_files(tmp_path: Path) -> None:
    data = tmp_path / "_data"
    _write(data / mpi2021.SECTION_A, MPI_A, {"a1": STATE_LABELS})
    _write(data / mpi2021.SECTION_B, MPI_B)
    _write(data / mpi2021.SECTION_D, MPI_D)
    out_dir = tmp_path / "derived"
    assert mpi2021.main(["--data-dir", str(data), "--out-dir", str(out_dir)]) == 0
    assert len(pd.read_parquet(out_dir / "mpi2021.parquet")) == 6


# --- GHS W4 / W5 ------------------------------------------------------------------------


def _ghs_files(tmp_path: Path, key: str) -> ghs.Wave:
    real = ghs.WAVES[key]
    wave = ghs.Wave(
        source=real.source,
        disability_file=tmp_path / key / "d.dta",
        roster_file=tmp_path / key / "r.dta",
        cover_file=tmp_path / key / "a.dta",
        domains=real.domains,
        age=real.age,
        weight=real.weight,
    )
    seeing, hearing = real.domains["seeing"], real.domains["hearing"]
    others = [v for k, v in real.domains.items() if k not in ("seeing", "hearing")]
    base = {v: 1 for v in others}
    disability = [
        {"hhid": 1, "indiv": 1, seeing: 1, hearing: 1, **base},
        {"hhid": 1, "indiv": 2, seeing: 3, hearing: 1, **base},  # disability3 = 1
        {"hhid": 1, "indiv": 3, seeing: -1, hearing: 1, **base},  # too young code -> missing
        {"hhid": 2, "indiv": 1, seeing: 1, hearing: 2, **base},  # household without weight
    ]
    roster = [
        {"hhid": 1, "indiv": 1, "s1q2": 1, real.age: 30},
        {"hhid": 1, "indiv": 2, "s1q2": 2, real.age: 70},
        {"hhid": 1, "indiv": 3, "s1q2": 2, real.age: 8},
        {"hhid": 2, "indiv": 1, "s1q2": 1, real.age: 40},
    ]
    cover = [
        {"hhid": 1, "state": CODE_OF["Oyo"], "sector": 2, "cluster": 77, "strata": 6,
         real.weight: 900.0},
        {"hhid": 2, "state": CODE_OF["Oyo"], "sector": 2, "cluster": 78, "strata": 6,
         real.weight: None},
    ]  # fmt: skip
    _write(wave.disability_file, disability)
    _write(wave.roster_file, roster)
    _write(wave.cover_file, cover, {"state": STATE_LABELS})
    return wave


@pytest.mark.parametrize("key", ["w4", "w5"])
def test_ghs_waves(tmp_path: Path, key: str) -> None:
    wave = _ghs_files(tmp_path, key)
    path = ghs.run(wave, tmp_path / "derived")
    out = pd.read_parquet(path)
    assert out["disability3"].tolist() == [0, 1, NA]
    assert out["seeing"].tolist() == [1, 3, NA]
    assert out["age_group"].tolist() == ["18+", "18+", "5-17"]
    assert set(out["psu"]) == {f"{wave.source}-77"}
    assert set(out["zone"]) == {"South West"}


def test_ghs_main_rejects_unknown_wave() -> None:
    with pytest.raises(SystemExit):
        ghs.main(["--waves", "w3"])
