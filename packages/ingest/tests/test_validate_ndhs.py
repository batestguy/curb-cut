"""The NDHS report reproduction (P4a step 0) on INVENTED rows; no real microdata."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import pandas as pd
import pytest
from curbcut_ingest import validate_ndhs as v


def _raw(rows: Sequence[Mapping[str, float]]) -> pd.DataFrame:
    base = {
        "hv005": 1_000_000, "hv025": 1, "hv103": 1, "hv104": 2, "hv105": 30, "hv270": 3,
        "shstate": 1,
        "hdis2": 1, "hdis4": 1, "hdis5": 1, "hdis6": 1, "hdis7": 1, "hdis8": 1, "hdis9": 1,
    }  # fmt: skip
    return pd.DataFrame([base | dict(row) for row in rows]).astype("float64")


def test_prepare_keeps_de_facto_5_plus_and_unknown_age() -> None:
    people = v.prepare(
        _raw([{}, {"hv103": 0}, {"hv105": 4}, {"hv105": 98}, {"hv105": 5}, {"hv105": 95}])
    )
    assert sorted(people["age"].tolist()) == [5, 30, 95, 98]


def test_unknown_age_counts_as_15_plus_but_in_no_age_band() -> None:
    people = v.prepare(_raw([{"hv105": 98, "hdis9": 3, "hdis2": 3}, {"hv105": 7}]))
    table = v.table_14_1(people)
    number = dict(zip(table["row"], table["number"], strict=True))
    severe = dict(zip(table["row"], table["a_lot_or_cannot"], strict=True))
    assert number["age_15_plus"] == 1
    assert number["total"] == 2
    assert number["age_60_plus"] == 0
    assert severe["age_15_plus"] == 100


def test_table_14_2_rates_are_weighted_and_dont_know_stays_in_denominator() -> None:
    rows = [
        {"hdis2": 2, "hdis9": 2, "hv005": 3_000_000},  # some difficulty seeing, weight 3
        {"hdis2": 3, "hdis7": 4, "hdis9": 4},  # two domains at 3+, weight 1
        {"hdis2": 8, "hdis9": 8},  # don't know, weight 1: in the denominator
        {"hv105": 10},  # child: not in the 15+ table
    ]
    table = v.table_14_2(v.prepare(_raw(rows)), {1: "Kano"})
    row = table[(table["sex"] == "female") & (table["state"] == "Kano")].iloc[0].to_dict()
    assert row["number"] == 5
    assert row["seeing"] == pytest.approx(80.0)  # weights 3 + 1 of 5
    assert row["walking"] == pytest.approx(20.0)
    assert row["some"] == pytest.approx(60.0)
    assert row["a_lot_or_cannot"] == pytest.approx(20.0)
    assert row["multi_domain"] == pytest.approx(20.0)
    assert row["no_difficulty"] == 0


def test_compare_allows_rounding_only() -> None:
    published = pd.DataFrame({"row": ["a", "b"], "rate": [2.1, 2.1], "number": [100.0, 100.0]})
    ours = pd.DataFrame(
        {"row": ["a", "b"], "rate": [2.149, 2.151], "number": [100.4, 99.4], "n_unweighted": 90}
    )
    result = v.compare(ours, published, ["row"])
    keys = zip(result["row"], result["column"], strict=True)
    ok = dict(zip(keys, result["ok"], strict=True))
    assert ok[("a", "rate")]
    assert not ok[("b", "rate")]
    assert ok[("a", "number")]
    assert not ok[("b", "number")]


def test_table_14_2_has_zone_residence_and_wealth_rows() -> None:
    rows = [{"hv025": 2, "hv270": 1}, {"hv025": 1, "hv270": 5, "hdis2": 3, "hdis9": 3}]
    table = v.table_14_2(v.prepare(_raw(rows)), {1: "Kano"}, {"Kano": "North West"})
    rate = dict(zip(table["state"], table["a_lot_or_cannot"], strict=True))
    assert rate["zone: North West"] == pytest.approx(50.0)
    assert rate["residence: urban"] == 100
    assert rate["residence: rural"] == 0
    assert rate["wealth: highest"] == 100  # hv270 = 5 is the richest quintile
    assert rate["wealth: lowest"] == 0
