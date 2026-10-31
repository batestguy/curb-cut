"""P5 exposure rules (pre-registration 3.2, S2, S3, S5, S6) on INVENTED rows only.

Nothing here comes from the real microdata: every row is made up to exercise one rule.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
from curbcut_ingest.restricted import common as c
from curbcut_ingest.restricted import p5_exposure as x
from curbcut_ingest.restricted.mpi2021 import SECTION_A, SECTION_B, SECTION_D

pyreadstat = pytest.importorskip("pyreadstat")

NO_DIFFICULTY = {"d9a": 1, "d10a": 1, "d11a": 1, "d12a": 1, "d13a": 1, "d14a": 1, "d15a": 1}
SCREEN_NO = {"d2": 2, "d2a": None, "d2b": None, "d3a": 2, "d3b": None, "d4b": None,
             "d5": 2, "d6a": None, "d8": None}  # fmt: skip


def _person(hh: int, line: int, **items: float | None) -> dict:
    return {"hh_id": hh, "d1": line, **SCREEN_NO, **NO_DIFFICULTY, **items}


def _d(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=x.D_COLUMNS).astype("float64")


def _status(definition: str, **items: float | None) -> dict:
    d = _d([_person(1, 1, **items)])
    return {k: v for k, v in x.person_domains(d, definition).iloc[0].items()}


def test_screened_routing_primary_vs_s5() -> None:
    # Screener yes, no aid: no severity was asked -> not severe (primary), severe (S5).
    unasked = {"d2": 1, "d2a": 2}
    assert _status("primary", **unasked)["seeing"] == 0
    assert _status("s5", **unasked)["seeing"] == 1
    # Screener yes, aid yes, "a lot even with glasses" -> severe in both.
    rated = {"d2": 1, "d2a": 1, "d2b": 3}
    assert _status("primary", **rated)["seeing"] == 1
    assert _status("s5", **rated)["seeing"] == 1
    # Aid user rated "some difficulty" -> not severe.
    assert _status("primary", d5=1, d6a=1, d8=2)["walking"] == 0
    # Aid user with no severity answer, or a don't-know (5) -> missing.
    assert pd.isna(_status("primary", d3a=1, d3b=1, d4b=None)["hearing"])
    assert pd.isna(_status("primary", d3a=1, d3b=1, d4b=5)["hearing"])
    # Screener no -> not severe even if a stray severity answer exists.
    assert _status("primary", d2=2, d2b=4)["seeing"] == 0
    # Screener missing -> missing.
    assert pd.isna(_status("primary", d2=None)["seeing"])


def test_scaled_domains_and_communication_worse_of() -> None:
    assert _status("primary", d11a=3)["selfcare"] == 1
    assert _status("primary", d12a=4)["cognition"] == 1
    assert _status("primary", d12a=2)["cognition"] == 0
    # Communication is the worse of understanding and being understood.
    assert _status("primary", d9a=1, d10a=3)["communication"] == 1
    # One item missing, the other below 3 -> the domain is unknown.
    assert pd.isna(_status("primary", d9a=None, d10a=2)["communication"])
    # Upper body and skin are not in the primary definition.
    assert set(_status("primary", d13a=4, d15a=4)) == set(x.PRIMARY_DOMAINS)


def test_s6_is_routing_free() -> None:
    status = _status("s6", d2=1, d2a=1, d2b=4, d11a=1)
    assert set(status) == set(x.SCALED_DOMAINS)
    assert all(v == 0 for v in status.values())  # severe seeing does not count in S6


def test_s2_broad_includes_some_difficulty_upper_body_skin_and_screener() -> None:
    assert _status("s2", d13a=2)["lifting"] == 1
    assert _status("s2", d14a=2)["hands"] == 1
    assert _status("s2", d15a=2)["skin"] == 1
    assert _status("s2", d12a=2)["cognition"] == 1
    assert _status("s2", d3a=1, d3b=2)["hearing"] == 1  # "yes", no aid: a difficulty
    assert all(v == 0 for v in _status("s2").values())
    # The primary definition ignores "some difficulty".
    assert _status("primary", d12a=2)["cognition"] == 0


def test_s2_reading_c_for_aid_users() -> None:
    """Reading C (2026-10-31): an aid user counts on the "even when using the aid" item at
    "some difficulty" or worse; "no difficulty" with the aid is not a difficulty."""
    assert _status("s2", d2=1, d2a=1, d2b=1)["seeing"] == 0
    assert _status("s2", d2=1, d2a=1, d2b=2)["seeing"] == 1
    assert _status("s2", d5=1, d6a=1, d8=4)["walking"] == 1
    assert pd.isna(_status("s2", d3a=1, d3b=1, d4b=None)["hearing"])  # aid, no answer
    assert pd.isna(_status("s2", d2=1, d2a=None)["seeing"])  # aid use unknown
    assert _status("s2", d2=2, d2b=4)["seeing"] == 0  # screener no
    # The same function serves every definition: threshold and unasked are parameters.
    scr, aid, sev = pd.Series([1.0, 1.0]), pd.Series([1.0, 2.0]), pd.Series([2.0, None])
    assert x.screened_status(scr, aid, sev, 0).tolist() == [0, 0]
    assert x.screened_status(scr, aid, sev, 1, x.SOME).tolist() == [1, 1]


ROSTER = pd.DataFrame(
    [
        # hh 1: unexposed (two complete, not-severe members; a child under 5 is ignored)
        {"hh_id": 1, "b1": 1, "b4a": 40, "b5": 1},
        {"hh_id": 1, "b1": 2, "b4a": 8, "b5": 3},
        {"hh_id": 1, "b1": 3, "b4a": 2, "b5": 3},
        # hh 2: exposed via the non-head member (self-care); head is fine
        {"hh_id": 2, "b1": 1, "b4a": 50, "b5": 1},
        {"hh_id": 2, "b1": 2, "b4a": 70, "b5": 9},
        # hh 3: a member 5+ with no Section D record, another severe -> exposed (D2)
        {"hh_id": 3, "b1": 1, "b4a": 30, "b5": 1},
        {"hh_id": 3, "b1": 2, "b4a": 12, "b5": 3},
        # hh 4: head severe in seeing (aid user)
        {"hh_id": 4, "b1": 1, "b4a": 60, "b5": 1},
        # hh 5: one member partly missing, nobody severe -> exposure missing (not excluded)
        {"hh_id": 5, "b1": 1, "b4a": 45, "b5": 1},
        # hh 6: screener yes, no aid -> unexposed in primary, exposed in S5
        {"hh_id": 6, "b1": 1, "b4a": 35, "b5": 1},
        # hh 7: no member 5+ in Section D -> out of the sample
        {"hh_id": 7, "b1": 1, "b4a": 3, "b5": 1},
        # hh 8: a member 5+ with no Section D record, nobody severe -> excluded
        {"hh_id": 8, "b1": 1, "b4a": 33, "b5": 1},
        {"hh_id": 8, "b1": 2, "b4a": 9, "b5": 3},
    ]
).astype("float64")

SECTION_D_ROWS = [
    _person(1, 1),
    _person(1, 2),
    _person(1, 3, d11a=4),  # age 2: recorded in D by mistake -> dropped, counted
    _person(2, 1),
    _person(2, 2, d11a=3),
    _person(3, 1, d12a=4),
    _person(4, 1, d2=1, d2a=1, d2b=3),
    _person(5, 1, d11a=None),
    _person(6, 1, d5=1, d6a=2, d15a=2),
    _person(8, 1),
]

WEIGHTS = [100, 200, 300, 400, 500, 600, 700, 800]
A = pd.DataFrame({"hh_id": range(1, 9), "pop_wgt": WEIGHTS}).astype("float64")
Q = pd.DataFrame({"hh_id": range(1, 9), "a9a": [1] * 8}).astype("float64")


def _build() -> pd.DataFrame:
    frame, _ = x.build(A, ROSTER, _d(SECTION_D_ROWS), Q)
    return frame.set_index("hh_id")


def test_household_rules() -> None:
    out = _build()
    assert out["exposed_primary"].tolist() == [0, 1, 1, 1, pd.NA, 0, pd.NA, pd.NA]
    # D2: a severe member makes the household exposed despite another's missing answers.
    assert out.loc["3", "reason_primary"] == x.EXPOSED
    assert out.loc["8", "reason_primary"] == x.MEMBER_ALL_MISSING
    assert out.loc["5", "reason_primary"] == x.MEMBER_PART_MISSING
    # The same rule in every household-level definition.
    for definition in ("s2", "s5", "s6"):
        assert out.loc["3", f"exposed_{definition}"] == 1, definition
        assert out.loc["3", f"reason_{definition}"] == x.EXPOSED, definition
        assert pd.isna(out.loc["8", f"exposed_{definition}"]), definition
        assert out.loc["8", f"reason_{definition}"] == x.MEMBER_ALL_MISSING, definition
    assert out.loc["8", "exposed_s3"] == 0  # the head answered, not severe
    assert out.loc["6", "exposed_s5"] == 1
    assert out.loc["6", "exposed_s6"] == 0
    assert out.loc["6", "exposed_s2"] == 1  # walking screener yes, and skin
    # S3: only the head counts; household 2's severe member is not the head.
    assert out.loc["2", "exposed_s3"] == 0
    assert out.loc["4", "exposed_s3"] == 1
    assert out.loc["3", "exposed_s3"] == 1  # the head is severe; the other member is irrelevant
    assert out.loc["5", "reason_s3"] == x.HEAD_MISSING
    # Household 7 has nobody 5+ in D: out of the sample.
    assert not out.loc["7", "in_sample"]
    assert out.loc["1", "n_members_5plus"] == 2


def test_members_under5_dropped_and_counted() -> None:
    _, members = x.build(A, ROSTER, _d(SECTION_D_ROWS), Q)
    assert members.dropped_under5_in_d == 1
    assert int((~members.frame["in_d"]).sum()) == 2  # households 3 and 8, line 2


def test_sample_requires_completed_interview_and_weight() -> None:
    q = Q.assign(a9a=[1, 6, 1, 1, 1, 1, 1, 1])
    a = A.assign(pop_wgt=[100, 200, 300, 0, 500, 600, 700, 800])
    frame, _ = x.build(a, ROSTER, _d(SECTION_D_ROWS), q)
    in_sample = frame.set_index("hh_id")["in_sample"]
    assert not in_sample["2"]  # refused
    assert not in_sample["4"]  # no weight
    assert in_sample["1"]


def test_exposure_shares_weight_people() -> None:
    frame = _build().reset_index()
    weights = pd.Series(WEIGHTS, index=frame.index, dtype="float64")
    shares = x.exposure_shares(frame, weights)
    # Primary: known in hh 1, 2, 3, 4, 6 (weights 100, 200, 300, 400, 600); exposed 2-4.
    assert shares["primary"].share == pytest.approx(100 * 900 / 1600)
    assert shares["primary"].households == 5
    assert shares["primary"].households_missing == 2  # 5 and 8 (7 is out of the sample)
    total = 2900  # every sample household: all but 7
    assert shares["primary"].weighted_missing == pytest.approx(100 * 1300 / total)
    assert shares["primary"].missing_by_reason == {
        x.MEMBER_ALL_MISSING: ("<30", pytest.approx(100 * 800 / total)),
        x.MEMBER_PART_MISSING: ("<30", pytest.approx(100 * 500 / total)),
    }


def test_nbs_check_tolerance() -> None:
    def shares(value: float) -> dict[str, x.Share]:
        return {"s2": x.Share("s2", value, 1, 0, 0.0)}

    assert x.nbs_check(shares(12.5))
    assert x.nbs_check(shares(9.5))
    assert not x.nbs_check(shares(12.6))


def test_main_check_on_invented_files(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    data = tmp_path / "_data"
    data.mkdir()
    pyreadstat.write_dta(A, str(data / SECTION_A))
    pyreadstat.write_dta(ROSTER, str(data / SECTION_B))
    pyreadstat.write_dta(_d(SECTION_D_ROWS), str(data / SECTION_D))
    pyreadstat.write_dta(Q, str(data / x.SECTION_Q))
    out = tmp_path / "derived"
    monkeypatch.setattr(c, "RESTRICTED", tmp_path)
    code = x.main(["--data-dir", str(data), "--out-dir", str(out), "--check"])
    assert code in (0, 1)  # invented data need not match NBS
    frame = pd.read_parquet(out / f"{x.NAME}.parquet")
    assert len(frame) == 8
    assert not any(col in frame.columns for col in ("poor", "score", "pop_wgt"))


def test_out_dir_must_be_in_the_restricted_zone(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    restricted = tmp_path / "restricted"
    monkeypatch.setattr(c, "RESTRICTED", restricted)
    assert x.restricted_out_dir(restricted / "derived") == (restricted / "derived").resolve()
    with pytest.raises(x.OutDirError):
        x.restricted_out_dir(tmp_path / "public")
    with pytest.raises(x.OutDirError):
        x.restricted_out_dir(restricted / ".." / "public")

    def boom(*_: object) -> None:
        raise AssertionError("nothing may be read before the out-dir check")

    monkeypatch.setattr(x, "read", boom)
    assert x.main(["--out-dir", str(tmp_path / "public"), "--check"]) == 2
    assert not (tmp_path / "public").exists()
