"""MPI 2021 household rebuild and WHO z-scores on INVENTED rows and synthetic tables.

Nothing here comes from the real microdata or from the WHO workbooks: every row is made
up to exercise one rule (cut-offs, routing, eligibility, missing data, weights, k).
"""

from __future__ import annotations

from fractions import Fraction
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from curbcut_ingest import who_growth as wg
from curbcut_ingest.restricted import mpi2021
from curbcut_ingest.restricted import mpi2021_poverty as m
from curbcut_ingest.states import StateLookup

pyreadstat = pytest.importorskip("pyreadstat")
NA = pd.NA
LOOKUP = StateLookup.from_seeds()
STATE_LABELS = {i + 1: name.upper() for i, name in enumerate(sorted(LOOKUP.states))}
LAGOS = {name: i + 1 for i, name in enumerate(sorted(LOOKUP.states))}["Lagos"]


def _table(lam: float, mu: float, sigma: float) -> pd.DataFrame:
    days = range(wg.MAX_DAY + 1)
    frame = pd.DataFrame({"Day": days, "L": lam, "M": mu, "S": sigma})
    return wg.check_table(frame)


# Height-for-age: z = (y - 50) / 5. Weight-for-age: z = (y - 10) / 1 inside +/-3 SD.
TABLES = {
    ("lhfa", "male"): _table(1, 50, 0.1),
    ("lhfa", "female"): _table(1, 50, 0.1),
    ("wfa", "male"): _table(1, 10, 0.1),
    ("wfa", "female"): _table(1, 10, 0.1),
}


def _f(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows).astype("float64")


# --- WHO z-scores ---------------------------------------------------------------------


def test_lms_z_box_cox_and_log() -> None:
    y = np.array([55.0, 50.0])
    assert wg.lms_z(y, np.array([1.0, 1.0]), np.array([50.0, 50.0]), np.array([0.1, 0.1])) == (
        pytest.approx([1.0, 0.0])
    )
    z = wg.lms_z(np.array([np.e * 10]), np.array([0.0]), np.array([10.0]), np.array([0.5]))
    assert z == pytest.approx([2.0])  # log(y / M) / S


def test_restricted_z_is_linear_beyond_three_sd() -> None:
    lam, mu, sigma = np.array([0.5]), np.array([10.0]), np.array([0.1])
    sd3 = wg.lms_value(3, lam, mu, sigma)[0]
    sd2 = wg.lms_value(2, lam, mu, sigma)[0]
    y = np.array([sd3 + (sd3 - sd2)])  # one "2-3 SD gap" beyond +3
    assert wg.restricted_z(y, lam, mu, sigma) == pytest.approx([4.0])
    inside = np.array([wg.lms_value(1.5, lam, mu, sigma)[0]])
    assert wg.restricted_z(inside, lam, mu, sigma) == pytest.approx([1.5])
    sdm3 = wg.lms_value(-3, lam, mu, sigma)[0]
    sdm2 = wg.lms_value(-2, lam, mu, sigma)[0]
    low = np.array([sdm3 - 0.5 * (sdm2 - sdm3)])
    assert wg.restricted_z(low, lam, mu, sigma) == pytest.approx([-3.5])


def test_zscores_lookup_flags_and_sex() -> None:
    sex = pd.Series(["male", "female", "male", None, "female"])
    days = pd.Series([100.0, 2000.0, 10.0, 10.0, 10.0])  # day 2000 is out of range
    height = pd.Series([45.0, 45.0, 10.0, 45.0, 60.0])
    z = wg.zscores(TABLES, "lhfa", sex, days, height)
    assert z.iloc[0] == pytest.approx(-1.0)
    assert np.isnan(z.iloc[1])  # beyond 1856 days
    assert np.isnan(z.iloc[2])  # z = -8: flagged (< -6)
    assert np.isnan(z.iloc[3])  # sex unknown
    assert z.iloc[4] == pytest.approx(2.0)
    waz = wg.zscores(TABLES, "wfa", pd.Series(["male"] * 2), pd.Series([5.0] * 2),
                     pd.Series([16.0, 14.5]))  # fmt: skip
    assert np.isnan(waz.iloc[0])  # z = 6 > 5: flagged for weight
    assert waz.iloc[1] == pytest.approx(4.5)


def test_age_and_position_correction() -> None:
    assert wg.age_days_from_months(pd.Series([0, 24, 59])).tolist() == [0, 730, 1796]
    lying = pd.Series([False, True, True, False, pd.NA], dtype="boolean")
    days = pd.Series([100.0, 800.0, 100.0, 800.0, 100.0])
    out = wg.standardised_height(pd.Series([60.0] * 5), lying, days)
    assert out.tolist() == pytest.approx([60.7, 59.3, 60.0, 60.0, 60.0])


def test_tables_are_checked(tmp_path: Path) -> None:
    with pytest.raises(wg.GrowthTableError, match="days"):
        wg.check_table(pd.DataFrame({"Day": [0, 1], "L": 1, "M": 1, "S": 1}))
    with pytest.raises(wg.GrowthTableError, match="missing"):
        wg.load_tables(tmp_path)
    for name in wg.FILES.values():
        (tmp_path / name).write_bytes(b"not the WHO file")
    with pytest.raises(wg.GrowthTableError, match="SHA-256"):
        wg.load_tables(tmp_path)


# --- weights and k ----------------------------------------------------------------------


def test_weights_from_table_2() -> None:
    assert sum(m.WEIGHTS.values()) == 1
    for indicators in m.DIMENSIONS.values():
        assert sum(m.WEIGHTS[k] for k in indicators) == Fraction(1, 4)
    assert all((w * m.POINTS).denominator == 1 for w in m.WEIGHTS.values())
    assert m.WEIGHTS["school_attendance"] == 3 * m.WEIGHTS["school_lag"]
    assert m.WEIGHTS["underemployment"] * 2 == m.WEIGHTS["unemployment"]


def test_score_and_poverty_cutoff() -> None:
    dep = pd.DataFrame(0, index=range(4), columns=m.INDICATORS, dtype="Int8")
    dep.loc[1, ["years_of_schooling", "nutrition"]] = 1  # 1/8 + 1/12 = 20.8%
    dep.loc[2, ["years_of_schooling", "nutrition", "water", "sanitation"]] = 1  # 29.2%
    dep.loc[3, "water"] = NA
    points = m.score_points(dep)
    assert points.tolist() == [0, 100, 140, NA]
    assert m.is_poor(points).tolist() == [0, 0, 1, NA]
    # k = 26% of 480 = 124.8 points: 124 is not poor, 125 is.
    assert m.is_poor(pd.Series([124, 125], dtype="Int16")).tolist() == [0, 1]


# --- household aggregation rules --------------------------------------------------------


def test_household_any_eligibility_and_two_thirds() -> None:
    households = pd.Index([1, 2, 3, 4, 5])
    hh = pd.Series([2, 3, 3, 3, 4, 4, 4, 5])
    dep = pd.Series([1, 0, 0, np.nan, 0, np.nan, np.nan, np.nan])
    out = m.household_any(hh, dep, households)
    # 1: no eligible member -> 0; 2: deprived; 3: 2 of 3 known -> 0; 4: 1 of 3 -> missing;
    # 5: nobody known -> missing
    assert out.tolist() == [0, 1, 0, NA, NA]


def test_household_none_achieved() -> None:
    households = pd.Index([1, 2, 3, 4, 5])
    hh = pd.Series([2, 2, 3, 3, 3, 4, 4, 4, 5])
    achieved = pd.Series([0, 0, 1, np.nan, np.nan, 0, np.nan, np.nan, 0])
    out = m.household_none_achieved(hh, achieved, households)
    # 1: no member 15+ -> 0; 2: nobody -> 1; 3: someone did, others unknown -> 0;
    # 4: 1 of 3 known and not achieved -> missing; 5: nobody -> 1
    assert out.tolist() == [0, 1, 0, NA, 1]


# --- indicators -------------------------------------------------------------------------


def test_food_insecurity_fies() -> None:
    rows = [[1] * 8, [1] * 7 + [2], [1] * 6 + [2] * 2, [1] * 6 + [None, 2], [1] * 4 + [None] * 2
            + [2] * 2, [None] * 8]  # fmt: skip
    e = pd.DataFrame(rows, columns=m.FIES).astype("float64")
    assert m.food_insecurity(e).tolist() == [1, 1, 0, NA, 0, NA]


def test_time_to_healthcare() -> None:
    f = _f([{"f1": 29}, {"f1": 30}, {"f1": None}])
    assert m.time_to_healthcare(f).tolist() == [0, 1, NA]


def test_attending_formal_school_only() -> None:
    roster = _f([
        {"b7": 2, "b10": None, "b11": None},  # never attended
        {"b7": 1, "b10": 2, "b11": None},  # not attending
        {"b7": 1, "b10": 1, "b11": 1},  # primary
        {"b7": 1, "b10": 1, "b11": 4},  # non-formal only
        {"b7": 1, "b10": 1, "b11": 0},  # preschool at school age
        {"b7": 1, "b10": 1, "b11": 8},  # level unknown
    ])  # fmt: skip
    assert m.attending(roster).tolist() == [0, 0, 1, 0, 0, NA]


def test_completed_primary() -> None:
    roster = _f([
        {"b7": 2, "b8": None, "b9": None},  # never attended
        {"b7": 1, "b8": 1, "b9": 15},  # primary 5
        {"b7": 1, "b8": 1, "b9": 16},  # primary 6
        {"b7": 1, "b8": 2, "b9": 20},  # started secondary
        {"b7": 1, "b8": 4, "b9": None},  # non-formal: counted as completed (Table 9)
        {"b7": 1, "b8": 0, "b9": 3},  # preschool
        {"b7": 1, "b8": 8, "b9": None},  # don't know
    ])  # fmt: skip
    assert m.completed_primary(roster).tolist() == [0, 0, 1, 1, 1, 0, NA]


def test_school_lag() -> None:
    roster = _f([
        {"b4a": 8, "b11": 1, "b12": 11},  # age 8 in Primary 1: 2 behind
        {"b4a": 8, "b11": 1, "b12": 12},  # age 8 in Primary 2: 1 behind
        {"b4a": 17, "b11": 2, "b12": 24},  # 17 in SS1 (grade 10, expected 12)
        {"b4a": 17, "b11": 2, "b12": 25},  # 17 in SS2
        {"b4a": 16, "b11": 3, "b12": 31},  # higher education
        {"b4a": 12, "b11": 2, "b12": None},  # grade unknown
    ])  # fmt: skip
    assert m.lagging(roster).tolist() == [1, 0, 1, 0, 0, NA]


def test_education_household_level() -> None:
    households = pd.Index([1, 2, 3])
    roster = _f([
        {"hh_id": 1, "b4a": 40, "b7": 1, "b8": 2, "b9": 26, "b10": None, "b11": None, "b12": None},
        {"hh_id": 1, "b4a": 9, "b7": 1, "b8": 1, "b9": None, "b10": 1, "b11": 1, "b12": 11},
        {"hh_id": 2, "b4a": 30, "b7": 2, "b8": None, "b9": None, "b10": None, "b11": None,
         "b12": None},
        {"hh_id": 2, "b4a": 10, "b7": 1, "b8": 4, "b9": None, "b10": 1, "b11": 4, "b12": None},
        {"hh_id": 3, "b4a": 16, "b7": 1, "b8": 1, "b9": 16, "b10": 1, "b11": 2, "b12": 25},
    ])  # fmt: skip
    out = m.education(roster, households)
    assert out["school_attendance"].tolist() == [0, 1, 0]  # 16-year-old is not 6-15
    assert out["years_of_schooling"].tolist() == [0, 1, 0]
    assert out["school_lag"].tolist() == [1, 0, 0]  # non-formal pupil is not assessed


def test_water_sanitation_housing_fuel_assets() -> None:
    i = _f([
        {"i1": 1, "i2": 1, "i2a": 24, "i2b": 30, "i4": 1, "i5": 2},
        {"i1": 13, "i2": None, "i2a": None, "i2b": None, "i4": 12, "i5": None},
        {"i1": 15, "i2": 2, "i2a": None, "i2b": None, "i4": 7, "i5": 1},
        {"i1": 5, "i2": 1, "i2a": 3, "i2b": 30, "i4": 3, "i5": 2},
        {"i1": 5, "i2": 1, "i2a": 24, "i2b": 19, "i4": None, "i5": None},
    ])  # fmt: skip
    assert m.water(i).tolist() == [0, 1, 1, 0, 0]  # sachet water is not improved
    assert m.water_reliability(i).tolist() == [0, 0, 1, 1, 1]  # surface water: not asked
    assert m.sanitation(i).tolist() == [0, 1, 1, 0, NA]  # shared improved -> deprived
    j = _f([
        {"j1": 8, "j2": 7, "j3": 13, "j4": 2},
        {"j1": 1, "j2": 7, "j3": 13, "j4": 7},
        {"j1": 8, "j2": 2, "j3": None, "j4": 8},
        {"j1": 8, "j2": 7, "j3": None, "j4": 9},
        {"j1": 96, "j2": 96, "j3": 96, "j4": 6},
    ])  # fmt: skip
    assert m.housing(j).tolist() == [0, 1, 1, NA, 0]  # "other" counts as not rudimentary
    assert m.cooking_fuel(j).tolist() == [0, 1, 1, 0, 0]  # crop residue, straw not named
    items = [v for vs in m.ASSET_ITEMS.values() for v in vs]
    base = dict.fromkeys(items, 2) | {m.CAR: 2}
    k = _f([
        base,
        base | {"k1m": 1},
        base | {"k1m": 1, "k2a": 1},
        base | {"k1a": 1, "k2j": 1},  # one computer, asked twice: counted once
        base | {m.CAR: 1},
        base | {"k1m": None},  # at most one asset even if owned: deprived
        base | {"k1m": None, "k2a": 1},  # could be two: unknown
        base | {"k1m": 1, "k2a": 1, m.CAR: None},  # two assets: car does not matter
    ])  # fmt: skip
    assert m.assets(k).tolist() == [1, 1, 0, 1, 0, 1, NA, 0]


def test_work_indicators() -> None:
    people = _f([
        {"c0": 0, "c6": 1, "c7": 1, "c9": None, "c10": None, "c11": None},  # unemployed
        {"c0": 0, "c6": 1, "c7": 2, "c9": None, "c10": None, "c11": None},  # not available
        {"c0": 1, "c6": None, "c7": None, "c9": 20, "c10": 1, "c11": 1},  # underemployed
        {"c0": 1, "c6": None, "c7": None, "c9": 20, "c10": 1, "c11": 2},  # not available
        {"c0": 1, "c6": None, "c7": None, "c9": 45, "c10": None, "c11": None},  # full time
        {"c0": None, "c6": None, "c7": None, "c9": None, "c10": None, "c11": None},  # missing
    ])  # fmt: skip
    assert m.unemployed(people).tolist() == [1, 0, 0, 0, 0, NA]
    assert m.underemployed(people).tolist() == [0, 0, 1, 0, 0, NA]


def test_security_shock() -> None:
    h2 = pd.DataFrame(
        [[2] * 8, [2] * 7 + [1], [3] + [2] * 7, [3] + [1] + [2] * 6], columns=m.SHOCKS
    ).astype("float64")
    assert m.security_shock(h2).tolist() == [0, 1, NA, 1]


def test_adult_underweight_and_nutrition() -> None:
    adults = _f([
        {"hh_id": 1, "q12b": 30, "q13": 1, "q14": 50, "q15": 170},  # BMI 17.3
        {"hh_id": 2, "q12b": 30, "q13": 4, "q14": 70, "q15": 170},  # BMI 24.2
        {"hh_id": 3, "q12b": 16, "q13": 1, "q14": 40, "q15": 170},  # under 18: not eligible
        {"hh_id": 4, "q12b": 30, "q13": 2, "q14": None, "q15": None},  # not present
    ])  # fmt: skip
    flags = m.adult_underweight(adults)
    assert flags["hh_id"].tolist() == [1, 2]
    assert flags["undernourished"].tolist() == [1, 0]
    kids = pd.DataFrame({"hh_id": [2, 3], "undernourished": [1, NA]}).astype(
        {"undernourished": "Int8"}
    )
    out = m.nutrition(kids, flags, pd.Index([1, 2, 3, 4]))
    assert out.tolist() == [1, 1, 0, 0]  # nobody validly measured -> non-deprived


def test_child_undernourished_uses_roster_age_and_sex() -> None:
    roster = _f([
        {"hh_id": 1, "b1": 2, "b3": 1, "b4b": 40},
        {"hh_id": 1, "b1": 3, "b3": 2, "b4b": 10},
        {"hh_id": 2, "b1": 2, "b3": 1, "b4b": 30},
    ])  # fmt: skip
    children = _f([
        {"hh_id": 1, "t0": 2, "t1a": 1, "t1b": 10, "t1c": 2, "t1d": 35},  # HAZ -3: stunted
        {"hh_id": 1, "t0": 3, "t1a": 1, "t1b": 9.5, "t1c": 1, "t1d": 50},  # fine
        {"hh_id": 2, "t0": 2, "t1a": 2, "t1b": None, "t1c": None, "t1d": None},  # not present
    ])  # fmt: skip
    out = m.child_undernourished(children, roster, TABLES)
    assert out["hh_id"].tolist() == [1, 1]
    assert out["undernourished"].tolist() == [1, 0]


# --- household build, confounders, national figures, CLI ---------------------------------

SECTIONS_ROWS: dict[str, list[dict]] = {
    mpi2021.SECTION_A: [
        {"hh_id": 1, "a1": LAGOS, "a1b": 241, "a3": 1, "a4": 11, "hhsize": 2, "hh_wgt": 500,
         "pop_wgt": 1000},
        {"hh_id": 2, "a1": LAGOS, "a1b": 242, "a3": 2, "a4": 12, "hhsize": 3, "hh_wgt": 1000,
         "pop_wgt": 3000},
        {"hh_id": 3, "a1": LAGOS, "a1b": 241, "a3": 1, "a4": 11, "hhsize": 2, "hh_wgt": 250,
         "pop_wgt": 500},
        {"hh_id": 4, "a1": LAGOS, "a1b": 241, "a3": 1, "a4": 11, "hhsize": None,
         "hh_wgt": None, "pop_wgt": None},  # not interviewed
    ],
    mpi2021.SECTION_B: [
        {"hh_id": 1, "b1": 1, "b3": 1, "b4a": 40, "b4b": None, "b5": 1, "b7": 1, "b8": 2,
         "b9": 26, "b10": None, "b11": None, "b12": None},
        {"hh_id": 1, "b1": 2, "b3": 2, "b4a": 35, "b4b": None, "b5": 2, "b7": 1, "b8": 2,
         "b9": 23, "b10": None, "b11": None, "b12": None},
        {"hh_id": 2, "b1": 1, "b3": 2, "b4a": 50, "b4b": None, "b5": 1, "b7": 2, "b8": None,
         "b9": None, "b10": None, "b11": None, "b12": None},
        {"hh_id": 2, "b1": 2, "b3": 1, "b4a": 3, "b4b": 40, "b5": 3, "b7": None, "b8": None,
         "b9": None, "b10": None, "b11": None, "b12": None},
        {"hh_id": 2, "b1": 3, "b3": 2, "b4a": 10, "b4b": None, "b5": 3, "b7": 2, "b8": None,
         "b9": None, "b10": None, "b11": None, "b12": None},
        {"hh_id": 3, "b1": 2, "b3": 2, "b4a": 28, "b4b": None, "b5": 1, "b7": 1, "b8": 1,
         "b9": 14, "b10": None, "b11": None, "b12": None},
        {"hh_id": 3, "b1": 1, "b3": 1, "b4a": 65, "b4b": None, "b5": 1, "b7": 1, "b8": 3,
         "b9": 35, "b10": None, "b11": None, "b12": None},
    ],
    m.SECTION_C: [
        {"hh_id": 1, "c00": 1, "c0": 1, "c6": None, "c7": None, "c9": 45, "c10": None,
         "c11": None},
        {"hh_id": 1, "c00": 2, "c0": 0, "c6": 2, "c7": 2, "c9": None, "c10": None, "c11": None},
        {"hh_id": 2, "c00": 1, "c0": 0, "c6": 1, "c7": 1, "c9": None, "c10": None, "c11": None},
        {"hh_id": 3, "c00": 1, "c0": 1, "c6": None, "c7": None, "c9": 50, "c10": None,
         "c11": None},
        {"hh_id": 3, "c00": 2, "c0": 1, "c6": None, "c7": None, "c9": 50, "c10": None,
         "c11": None},
    ],
    m.SECTION_E: [{"hh_id": h, **dict.fromkeys(m.FIES, v)} for h, v in ((1, 2), (2, 1), (3, 2))],
    m.SECTION_F: [{"hh_id": 1, "f1": 10}, {"hh_id": 2, "f1": 60}, {"hh_id": 3, "f1": 10}],
    m.SECTION_H2: [
        {"hh_id": 1, **dict.fromkeys(m.SHOCKS, 2)},
        {"hh_id": 2, **dict.fromkeys(m.SHOCKS, 2), "h21": 1},
        {"hh_id": 3, **dict.fromkeys(m.SHOCKS, 3)},  # don't know throughout -> missing
    ],
    m.SECTION_I: [
        {"hh_id": 1, "i1": 1, "i2": 1, "i2a": 24, "i2b": 30, "i4": 1, "i5": 2},
        {"hh_id": 2, "i1": 13, "i2": None, "i2a": None, "i2b": None, "i4": 12, "i5": None},
        {"hh_id": 3, "i1": 1, "i2": 1, "i2a": 24, "i2b": 30, "i4": 1, "i5": 2},
    ],
    m.SECTION_J: [
        {"hh_id": 1, "j1": 8, "j2": 7, "j3": 13, "j4": 2},
        {"hh_id": 2, "j1": 1, "j2": 2, "j3": 3, "j4": 7},
        {"hh_id": 3, "j1": 8, "j2": 7, "j3": 13, "j4": 2},
    ],
    m.SECTION_K: [
        {"hh_id": 1, **dict.fromkeys(m.COLUMNS[m.SECTION_K][1:], 2), "k1m": 1, "k1n": 1},
        {"hh_id": 2, **dict.fromkeys(m.COLUMNS[m.SECTION_K][1:], 2)},
        {"hh_id": 3, **dict.fromkeys(m.COLUMNS[m.SECTION_K][1:], 2), "k2e": 1},
    ],
    m.SECTION_R: [{"hh_id": 1, "q12b": 40, "q13": 1, "q14": 70, "q15": 175}],
    m.SECTION_T: [{"hh_id": 2, "t0": 2, "t1a": 1, "t1b": 10, "t1c": 2, "t1d": 35}],
}  # fmt: skip


def _sections() -> dict[str, pd.DataFrame]:
    return {name: _f(rows) for name, rows in SECTIONS_ROWS.items()}


def test_build_household_frame() -> None:
    out = m.build(_sections(), TABLES, STATE_LABELS, LOOKUP).set_index("hh_id")
    assert out.index.tolist() == ["1", "2", "3"]  # household 4 (no weight) dropped
    assert not any(
        col.startswith("mpi_") or col[:2] in {"d1", "d2", "d3"} for col in map(str, out.columns)
    )
    assert set(out["state"]) == {"Lagos"}
    assert out.loc["2", "stratum"] == f"mpi2021-{LAGOS}-242-2"
    assert out.loc["2", "psu"] == "mpi2021-12"
    assert out.loc["2", "person_weight"] == 1000.0  # pop_wgt / hhsize
    hh2 = list(out.loc["2", [f"d_{k}" for k in m.INDICATORS]])
    assert hh2 == [1, 1, 1, 1, 1, 0, 1, 0, 1, 1, 1, 1, 1, 0, 1]
    assert out.loc["2", "score"] == pytest.approx(421 / 480)
    assert out["poor"].tolist() == [0, 1, NA]
    assert out.loc["3", "n_missing"] == 1  # security shock unknown
    # confounders
    assert list(out.loc["2", ["n_0_4", "n_5_14", "n_15_59", "n_60plus"]]) == [1, 1, 1, 0]
    assert list(out.loc["2", ["head_sex", "head_age", "head_education"]]) == [
        "female", 50, "none"]  # fmt: skip
    assert out.loc["3", "n_heads"] == 2  # two heads: the lowest line number is used
    assert list(out.loc["3", ["head_sex", "head_age", "head_education"]]) == [
        "male", 65, "higher"]  # fmt: skip
    assert out.loc["1", "head_education"] == "secondary"


def test_national_weights_people_and_skips_incomplete() -> None:
    frame = m.build(_sections(), TABLES, STATE_LABELS, LOOKUP)
    result = m.national(frame)
    assert (result.households, result.households_used) == (3, 2)
    assert result.headline["H"] == pytest.approx(75.0)  # 3000 / (1000 + 3000)
    assert result.headline["A"] == pytest.approx(100 * 421 / 480)
    assert result.headline["MPI"] == pytest.approx(0.75 * 421 / 480)
    assert result.uncensored["water"] == pytest.approx(75.0)
    assert result.censored["school_lag"] == 0.0
    assert m.within_tolerance(result) == {"H": False, "A": False, "MPI": False}


def test_main_on_invented_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    data = tmp_path / "_data"
    data.mkdir()
    for name, rows in SECTIONS_ROWS.items():
        labels = {"a1": STATE_LABELS} if name == mpi2021.SECTION_A else {}
        pyreadstat.write_dta(_f(rows), str(data / name), variable_value_labels=labels)
    monkeypatch.setattr(wg, "load_tables", lambda directory: TABLES)
    out_dir = tmp_path / "derived"
    args = ["--data-dir", str(data), "--out-dir", str(out_dir)]
    assert m.main(args) == 0  # Section D is not there and is never needed
    frame = pd.read_parquet(out_dir / f"{m.NAME}.parquet")
    assert len(frame) == 3
    assert m.main([*args, "--validate"]) == 1  # invented data cannot match the report


@pytest.mark.skipif(
    not all((wg.WHO_DIR / name).is_file() for name in wg.FILES.values()),
    reason="WHO workbooks not in data/sources/who-growth/ (git-ignored, local only)",
)
def test_real_who_tables_reproduce_their_sd_columns() -> None:
    """The WHO workbooks print the measurement at -4..+4 SD; our z must give those back.

    Public WHO reference tables, not microdata. Differences come only from the 3-decimal
    rounding of the printed SD columns.
    """
    tables = wg.load_tables()
    nominal = {"SD4neg": -4, "SD3neg": -3, "SD2neg": -2, "SD1neg": -1, "SD0": 0,
               "SD1": 1, "SD2": 2, "SD3": 3, "SD4": 4}  # fmt: skip
    for (indicator, sex), name in wg.FILES.items():
        full = pd.read_excel(wg.WHO_DIR / name)
        days = full["Day"].astype("float64")
        sexes = pd.Series(sex, index=full.index)
        for column, z in nominal.items():
            got = wg.zscores(tables, indicator, sexes, days, full[column])
            lo, hi = wg.FLAGS[indicator]
            if lo <= z <= hi:
                assert got.notna().all(), (name, column)
            assert float((got.dropna() - z).abs().max()) < 0.002, (name, column)
