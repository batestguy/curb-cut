"""Shared helpers of the restricted-zone harmonisers, on invented values only."""

from __future__ import annotations

import pandas as pd
import pytest
from curbcut_ingest.restricted import common as c
from curbcut_ingest.states import StateLookup, UnknownStateError, state_key

NA = pd.NA


def test_masked_hides_small_counts() -> None:
    assert c.masked(0) == "0"
    assert c.masked(1) == "<30"
    assert c.masked(29) == "<30"
    assert c.masked(30) == "30"
    assert c.masked(12345) == "12,345"


def test_wg_scale_keeps_only_1_to_4() -> None:
    values = pd.Series([1, 2, 3, 4, 5, 8, -1, None, 2.0])
    assert c.wg_scale(values).tolist() == [1, 2, 3, 4, NA, NA, NA, NA, 2]


def test_worse_of_rules() -> None:
    a = pd.Series([1, 3, 1, None, None, 2], dtype="Int8")
    b = pd.Series([2, None, None, 4, None, 2], dtype="Int8")
    # 3+ on either item is enough; otherwise both must be answered.
    assert c.worse_of(a, b).tolist() == [2, 3, NA, 4, NA, 2]


def test_disability3_follows_wg_doc_7a() -> None:
    rows = [
        [1, 1, 1, 1, 1, 1],  # all answered, none 3+ -> 0
        [1, 2, 2, 1, 1, 1],  # some difficulty only -> 0
        [1, 1, 3, 1, 1, 1],  # a lot of difficulty -> 1
        [4, None, None, None, None, None],  # cannot do one, rest missing -> 1
        [1, 1, None, 1, 1, 1],  # one missing, none 3+ -> missing
        [None] * 6,  # nothing answered -> missing
    ]
    frame = pd.DataFrame(rows, columns=list(c.WG_DOMAINS), dtype="Int8")
    assert c.disability3(frame).tolist() == [0, 0, 1, 1, NA, NA]


def test_age_group_and_band() -> None:
    ages = pd.Series([3, 5, 9, 10, 17, 18, 29, 30, 49, 50, 64, 65, 97, None])
    assert c.age_group(ages).tolist() == [NA, "5-17", "5-17", "5-17", "5-17"] + ["18+"] * 8 + [NA]
    assert c.age_band(ages).tolist() == [
        NA,
        "5-9",
        "5-9",
        "10-17",
        "10-17",
        "18-29",
        "18-29",
        "30-49",
        "30-49",
        "50-64",
        "50-64",
        "65+",
        "65+",
        NA,
    ]


def test_recode_and_codes() -> None:
    assert c.recode(pd.Series([1, 2, 9, None]), c.SEX).tolist() == ["male", "female", NA, NA]
    assert c.code_text(pd.Series([12.0, 3.0, None])).tolist() == ["12", "3", NA]
    assert c.code_text(pd.Series(["A1 ", "B2"])).tolist() == ["A1", "B2"]
    joined = c.join_codes("x", pd.Series([1.0, 2.0]), pd.Series([7, 8]))
    assert joined.tolist() == ["x-1-7", "x-2-8"]


def test_safe_main_withholds_messages(capsys: pytest.CaptureFixture[str]) -> None:
    @c.safe_main
    def boom() -> int:
        raise ValueError("secret value 12345")

    assert boom() == 1
    err = capsys.readouterr().err
    assert "ValueError" in err
    assert "12345" not in err
    assert "withheld" in err


def test_report_helpers_mask(capsys: pytest.CaptureFixture[str]) -> None:
    c.report_counts("x", pd.Series([1] * 40 + [2] * 3 + [None], dtype="Int64"))
    c.report_match("join", 5, 100)
    out = capsys.readouterr().out
    assert "1: 40" in out
    assert "2: <30" in out
    assert "missing: <30" in out
    assert "<30 of 100 matched" in out


def test_read_dta_reads_named_columns_only(tmp_path) -> None:
    pyreadstat = pytest.importorskip("pyreadstat")
    path = tmp_path / "x.dta"
    frame = pd.DataFrame({"a": [1.0, 2.0], "b": [3.0, 4.0], "s": [1.0, 2.0]})
    pyreadstat.write_dta(frame, str(path), variable_value_labels={"s": {1: "ABIA", 2: "FCT"}})
    got, meta = c.read_dta(path, ["a", "s"])
    assert list(got.columns) == ["a", "s"]
    assert c.value_labels(meta, "s") == {1: "ABIA", 2: "FCT"}
    with pytest.raises(KeyError):
        c.read_dta(path, ["missing"])


def test_write_parquet(tmp_path) -> None:
    path = c.write_parquet(pd.DataFrame({"a": [1, 2]}), "t", tmp_path)
    assert pd.read_parquet(path)["a"].tolist() == [1, 2]


def test_state_lookup_from_seeds() -> None:
    lookup = StateLookup.from_seeds()
    assert len(lookup.states) == 37
    assert state_key(" 1. Abia ") == "abia"
    assert lookup.resolve("FCT ABUJA").state == "Federal Capital Territory"
    assert lookup.resolve("37. FCT").state_code == "NG-FC"
    assert lookup.resolve("akwa ibom").zone == "South South"
    with pytest.raises(UnknownStateError):
        lookup.resolve("Atlantis")


def test_map_codes_needs_all_37() -> None:
    lookup = StateLookup.from_seeds()
    labels = {i + 1: name for i, name in enumerate(sorted(lookup.states))}
    assert len(lookup.map_codes(labels)) == 37
    labels.pop(1)
    with pytest.raises(UnknownStateError):
        lookup.map_codes(labels)
