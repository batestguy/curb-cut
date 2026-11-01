"""Rebuild the Nigeria MPI (2022) at household level from the NBS MPI 2021 microdata.

NBS ships no MPI score or poverty flag (``docs/verification.md`` D61), so the index is
rebuilt from the 15 indicators of Table 2 of *Nigeria Multidimensional Poverty Index
(2022)* (NBS/OPHI), weights as read from the rendered page (D64). A household is poor
when its weighted deprivation score is at least k = 26%; every member shares the
household's status, so national figures weight each household by its people
(``pop_wgt``).

**No disability item is read here.** Section D is never opened and the output has no
disability column; the poverty-by-disability analysis waits for the pre-registration
(PLAN.md P5 step 17).

Rules the report does not state are taken from OPHI's global-MPI conventions and listed
in D64: a household with no eligible member for a person-based indicator is non-deprived;
"any member deprived" indicators use the members with data, and are missing when no one is
deprived and fewer than two-thirds of the eligible members have data ("some member
achieved" for years of schooling likewise); a question skipped by the questionnaire's
routing counts as not deprived; a household missing any indicator is left out of the
national figures. Weights: ``hh_wgt``; ``pop_wgt`` (household weight x size, calibrated
per state); person weight ``pop_wgt / hhsize`` as in :mod:`mpi2021`.

Design (assumption, D40): strata = state ``a1`` x senatorial district ``a1b`` x sector
``a3``; PSU = EA ``a4``.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

import numpy as np
import pandas as pd

from curbcut_ingest import who_growth
from curbcut_ingest.restricted import common as c
from curbcut_ingest.restricted.mpi2021 import DATA_DIR, SECTION_A, SECTION_B, SOURCE
from curbcut_ingest.states import StateLookup

NAME = "mpi2021_household"
SECTION_C = "SECTION C_ ECONOMIC ACTIVITY AND WORK HISTORY.dta"
SECTION_E = "SECTION E_FOOD SECURITY.dta"
SECTION_F = "SECTION F_HEALTH.dta"
SECTION_H2 = "SECTION H2_ SAFETY AND SECURITY.dta"
SECTION_I = "SECTION I_ WATER AND SANITATION.dta"
SECTION_J = "SECTION J_HOUSING CHARACTERISTICS_NEW.dta"
SECTION_K = "SECTION K_HOUSEHOLD ASSETS.dta"
SECTION_Q = "SECTION Q_HOUSEHOLD RESPONSE STATUS.dta"
SECTION_R = "SECTION R_ADULT NUTRITION ANTHROPOMETRY.dta"
SECTION_T = "SECTION T_CHILDREN NUTRITION ANTHROPOMETRY.dta"

FIES = [f"e1{x}" for x in "abcdefgh"]
SHOCKS = [f"h2{i}" for i in range(1, 9)]
ASSET_ITEMS = {
    # Table 2 footnote 11; "PC" is either of the two computer questions, counted once.
    "radio": ["k1m"],
    "tv": ["k1n"],
    "refrigerator": ["k1c"],
    "bicycle": ["k2b"],
    "motorbike": ["k2c"],
    "landline": ["k1b"],
    "mobile": ["k2a"],
    "computer": ["k1a", "k2j"],
    "animal_cart": ["k2d"],
}
CAR = "k2e"

COLUMNS = {
    SECTION_A: ["hh_id", "a1", "a1b", "a3", "a4", "hhsize", "hh_wgt", "pop_wgt"],
    SECTION_B: ["hh_id", "b1", "b3", "b4a", "b4b", "b5", "b7", "b8", "b9", "b10", "b11", "b12"],
    SECTION_C: ["hh_id", "c00", "c0", "c6", "c7", "c9", "c10", "c11"],
    SECTION_E: ["hh_id", *FIES],
    SECTION_F: ["hh_id", "f1"],
    SECTION_H2: ["hh_id", *SHOCKS],
    SECTION_I: ["hh_id", "i1", "i2", "i2a", "i2b", "i4", "i5"],
    SECTION_J: ["hh_id", "j1", "j2", "j3", "j4"],
    SECTION_K: ["hh_id", *(v for vs in ASSET_ITEMS.values() for v in vs), CAR],
    SECTION_Q: ["hh_id", "a9a"],
    SECTION_R: ["hh_id", "q12b", "q13", "q14", "q15"],
    SECTION_T: ["hh_id", "t0", "t1a", "t1b", "t1c", "t1d"],
}

# --- the index: Table 2 (pp. 17-18), weights checked against the page image ------------

WEIGHTS: dict[str, Fraction] = {
    "nutrition": Fraction(1, 12),
    "food_insecurity": Fraction(1, 12),
    "time_to_healthcare": Fraction(1, 12),
    "school_attendance": Fraction(3, 32),
    "years_of_schooling": Fraction(1, 8),
    "school_lag": Fraction(1, 32),
    "water": Fraction(1, 24),
    "water_reliability": Fraction(1, 24),
    "sanitation": Fraction(1, 24),
    "housing": Fraction(1, 24),
    "cooking_fuel": Fraction(1, 24),
    "assets": Fraction(1, 24),
    "unemployment": Fraction(1, 10),
    "underemployment": Fraction(1, 20),
    "security_shock": Fraction(1, 10),
}
INDICATORS = list(WEIGHTS)
DIMENSIONS = {
    "health": INDICATORS[0:3],
    "education": INDICATORS[3:6],
    "living_standards": INDICATORS[6:12],
    "work_and_shocks": INDICATORS[12:15],
}
K = Fraction(26, 100)
POINTS = 480
"""Weights are whole multiples of 1/480, so scores are computed exactly in 480ths."""

PUBLISHED = {"H": 62.9, "A": 40.9, "MPI": 0.257}
"""Table 3 / D1 (national, k = 26%)."""
TOLERANCE = {"H": 1.0, "A": 1.0, "MPI": 0.010}
"""Fixed by the main session before the first run (2026-10-30): H and A in percentage
points, MPI in index units."""
PUBLISHED_UNCENSORED = {
    "nutrition": 34.9, "food_insecurity": 50.9, "time_to_healthcare": 49.1,
    "school_attendance": 28.3, "years_of_schooling": 13.5, "school_lag": 22.6,
    "water": 40.3, "water_reliability": 24.9, "sanitation": 63.7, "housing": 45.5,
    "cooking_fuel": 69.9, "assets": 30.4, "unemployment": 16.9, "underemployment": 20.4,
    "security_shock": 15.7,
}  # fmt: skip
"""Table D2: % of people deprived (poor or not)."""
PUBLISHED_CENSORED = {
    "nutrition": 28.7, "food_insecurity": 38.6, "time_to_healthcare": 38.7,
    "school_attendance": 26.3, "years_of_schooling": 13.0, "school_lag": 16.6,
    "water": 29.3, "water_reliability": 16.7, "sanitation": 46.5, "housing": 38.6,
    "cooking_fuel": 50.6, "assets": 25.9, "unemployment": 14.3, "underemployment": 15.9,
    "security_shock": 14.0,
}  # fmt: skip
"""Table D3: % of people poor and deprived."""

# Deprivation code lists (Table 2 footnotes 8-10 and the cut-off text).
UNIMPROVED_WATER = {7, 9, 10, 11, 12, 13, 15, 96}
"""Footnote 8: unprotected well, unprotected spring, rainwater, tanker truck, cart with
small tank, surface water, sachet water, other."""
UNIMPROVED_SANITATION = {4, 5, 8, 10, 11, 12, 96}
"""Footnote 9: flush to elsewhere / unknown, pit without slab, bucket, hanging, none, other."""
SHARED = 1
RUDIMENTARY_FLOOR = {1, 2, 3, 4}  # earth/sand, dung, wood planks, palm/bamboo
RUDIMENTARY_ROOF = {1, 2, 3, 4, 5, 6}  # none, thatch, rustic mat, palm/bamboo, planks, card
RUDIMENTARY_WALL = {1, 2, 3, 4, 5, 6, 7, 8, 9}  # none ... plywood, cardboard, reused wood
SOLID_FUEL = {5, 7, 8}
"""Dung, wood, charcoal/coal/lignite: the report's wording. Straw/grass (6) and crop
residue (9) are not named and are not counted."""
SOLID_FUEL_NO_CHARCOAL = {5, 6, 7, 9}
"""Outcome robustness (a) of the pre-registration (section 3.3; D64): dung, straw/grass,
wood, crop residue. Used only for ``poor_fuel_alt``; the index itself is unchanged."""
DONT_KNOW = 3
"""Section H2's "don't know" code."""

FIES_SEVERE = 7
HEALTH_MINUTES = 30
WATER_DAYS, WATER_HOURS = 20, 4
WORK_HOURS = 40
BMI_CUTOFF = 18.5
Z_CUTOFF = -2.0
ATTENDANCE_AGES = (6, 15)
SCHOOLING_AGE = 15
LAG_AGES = (8, 17)
PRIMARY_ENTRY_AGE = 6
LAG_YEARS = 2
WORK_AGE = 15
ADULT_AGES = (18, 60)
MIN_SHARE = Fraction(2, 3)

YES, NO = 1, 2
FORMAL_LEVELS = {1, 2, 3, 5}  # B11: primary, secondary, higher, technical
INFORMAL_LEVELS = {0, 4}  # B11: preschool, non-formal
HEAD = 1
MEASURED_CHILD = 1
MEASURED_ADULT = {1, 4}
LYING, STANDING = 1, 2

AGE_COUNTS = {"n_0_4": (0, 4), "n_5_14": (5, 14), "n_15_59": (15, 59), "n_60plus": (60, 200)}
P5_AGE_COUNTS = {
    # Pre-registration section 3.4: the MPI eligibility ages plus the very old.
    "n_0_4": (0, 4),
    "n_5": (5, 5),
    "n_6_14": (6, 14),
    "n_15_17": (15, 17),
    "n_18_59": (18, 59),
    "n_60_69": (60, 69),
    "n_70plus": (70, 200),
}
COMPLETED = 1
"""Section Q ``a9a``: 1 = completed interview (the P5 sample)."""
EDUCATION = {
    "none": "never attended school",
    "preschool": "preschool only",
    "non_formal": "non-formal education",
    "primary_incomplete": "primary, not completed",
    "primary": "completed primary",
    "secondary": "secondary (incl. technical)",
    "higher": "higher",
}


# --- helpers ------------------------------------------------------------------------


def _flag(condition: pd.Series, known: pd.Series) -> pd.Series:
    """1 where condition, 0 where known and not condition, missing otherwise."""
    out = pd.Series(pd.NA, index=condition.index, dtype="Int8")
    out[known.fillna(False).astype(bool)] = 0
    out[condition.fillna(False).astype(bool)] = 1
    return out


def _in(values: pd.Series, codes: set[int]) -> pd.Series:
    return c.to_num(values).isin(list(codes))


def household_any(
    hh_id: pd.Series, deprived: pd.Series, households: pd.Index, min_share: Fraction = MIN_SHARE
) -> pd.Series:
    """'Any eligible member deprived' at household level (OPHI conventions).

    ``deprived`` has one entry per eligible member (1, 0 or missing). Deprived if any
    member is 1; non-deprived if the household has no eligible member, or nobody is
    deprived and at least ``min_share`` of eligible members have data; missing otherwise.
    """
    frame = pd.DataFrame({"hh_id": hh_id.to_numpy(), "d": c.to_num(deprived).to_numpy()})
    grouped = frame.groupby("hh_id")["d"]
    any_dep = grouped.max().reindex(households)
    eligible = grouped.size().reindex(households).fillna(0)
    known = grouped.count().reindex(households).fillna(0)
    out = pd.Series(pd.NA, index=households, dtype="Int8")
    enough = (eligible == 0) | (known >= eligible * float(min_share))
    out[enough] = 0
    out[any_dep == 1] = 1
    return out


def household_none_achieved(
    hh_id: pd.Series, achieved: pd.Series, households: pd.Index, min_share: Fraction = MIN_SHARE
) -> pd.Series:
    """'No eligible member achieved' (years of schooling, OPHI convention).

    Non-deprived if any member achieved or there is no eligible member; deprived if nobody
    achieved and at least ``min_share`` of eligible members have data; missing otherwise.
    """
    frame = pd.DataFrame({"hh_id": hh_id.to_numpy(), "a": c.to_num(achieved).to_numpy()})
    grouped = frame.groupby("hh_id")["a"]
    some = grouped.max().reindex(households) == 1
    eligible = grouped.size().reindex(households).fillna(0)
    known = grouped.count().reindex(households).fillna(0)
    out = pd.Series(pd.NA, index=households, dtype="Int8")
    out[(eligible > 0) & (known >= eligible * float(min_share))] = 1
    out[(eligible == 0) | some] = 0
    return out


def _by_household(frame: pd.DataFrame, households: pd.Index) -> pd.DataFrame:
    """One row per household (first if duplicated), in ``households`` order."""
    return frame.drop_duplicates("hh_id").set_index("hh_id").reindex(households)


# --- health -------------------------------------------------------------------------


def child_undernourished(
    children: pd.DataFrame, roster: pd.DataFrame, tables: who_growth.Tables
) -> pd.DataFrame:
    """Per measured child: stunted (HAZ < -2) or underweight (WAZ < -2); 1/0/missing.

    Age and sex come from the roster (``t0`` = ``b1``); only ``t1a == 1`` (measured).
    """
    kids = children.merge(
        roster[["hh_id", "b1", "b3", "b4b"]],
        left_on=["hh_id", "t0"],
        right_on=["hh_id", "b1"],
        how="left",
        validate="many_to_one",
    )
    kids = kids[c.to_num(kids["t1a"]) == MEASURED_CHILD].copy()
    sex = c.recode(kids["b3"], c.SEX)
    days = who_growth.age_days_from_months(kids["b4b"])
    position = c.to_num(kids["t1c"])
    lying = pd.Series(pd.NA, index=kids.index, dtype="boolean")
    lying[position == LYING] = True
    lying[position == STANDING] = False
    height = who_growth.standardised_height(kids["t1d"], lying, days)
    haz = who_growth.zscores(tables, "lhfa", sex, days, height)
    waz = who_growth.zscores(tables, "wfa", sex, days, kids["t1b"])
    low = (haz < Z_CUTOFF) | (waz < Z_CUTOFF)
    kids["undernourished"] = _flag(low, haz.notna() & waz.notna())
    return kids[["hh_id", "undernourished"]]


def adult_underweight(adults: pd.DataFrame) -> pd.DataFrame:
    """Per measured adult aged 18-60: BMI < 18.5; 1/0/missing (BMI outside 10-80: missing)."""
    rows = adults[_in(adults["q13"], MEASURED_ADULT)].copy()
    age = c.to_num(rows["q12b"])
    rows = rows[(age >= ADULT_AGES[0]) & (age <= ADULT_AGES[1])]
    weight, height = c.to_num(rows["q14"]), c.to_num(rows["q15"]) / 100
    bmi = weight / height.where(height > 0) ** 2
    plausible = (bmi >= 10) & (bmi <= 80)
    rows["undernourished"] = _flag(bmi < BMI_CUTOFF, plausible).where(plausible)
    return rows[["hh_id", "undernourished"]]


def nutrition(
    child_flags: pd.DataFrame, adult_flags: pd.DataFrame, households: pd.Index
) -> pd.Series:
    """Deprived if any measured child or adult is undernourished; otherwise non-deprived,
    including households with nobody (validly) measured (OPHI convention)."""
    both = pd.concat([child_flags, adult_flags], ignore_index=True)
    measured = both[both["undernourished"].notna()]
    return household_any(measured["hh_id"], measured["undernourished"], households)


def food_insecurity(e: pd.DataFrame) -> pd.Series:
    """FIES: deprived with 7+ "yes" of 8; non-deprived when 7 can no longer be reached."""
    answers = e[FIES].apply(c.to_num)
    yes = (answers == YES).sum(axis=1)
    missing = (~answers.isin([YES, NO])).sum(axis=1)
    return _flag(yes >= FIES_SEVERE, yes + missing < FIES_SEVERE)


def time_to_healthcare(f: pd.DataFrame) -> pd.Series:
    """Minutes on foot to the nearest functional facility: deprived at 30 or more."""
    minutes = c.to_num(f["f1"])
    return _flag(minutes >= HEALTH_MINUTES, minutes >= 0)


# --- education ----------------------------------------------------------------------


def attending(roster: pd.DataFrame) -> pd.Series:
    """Attending (formal) school this year: 1/0/missing.

    Never attended or not attending -> 0. Attending at primary, secondary, higher or
    technical level -> 1; attending only preschool or non-formal education -> 0. This
    reproduces the report's own child-level figure (Table 8: 28.7% of children 6-15 out
    of school; D64). Attending at an unknown level -> missing.
    """
    b7, b10, b11 = (c.to_num(roster[v]) for v in ("b7", "b10", "b11"))
    out = pd.Series(pd.NA, index=roster.index, dtype="Int8")
    out[(b7 == NO) | (b10 == NO) | ((b10 == YES) & b11.isin(list(INFORMAL_LEVELS)))] = 0
    out[(b10 == YES) & b11.isin(list(FORMAL_LEVELS))] = 1
    return out


def completed_primary(roster: pd.DataFrame) -> pd.Series:
    """Completed primary school (six years): 1/0/missing.

    Never attended, preschool only, or primary below grade 6 -> 0; primary grade 6, or a
    secondary, technical or higher level -> 1. "Non-formal" as the highest level also
    counts as 1: that is what reproduces the report's Table 9 (all six cells within 0.1
    points; D64), although the report's text does not say so. "Don't know" or a primary
    grade not given -> missing.
    """
    b7, b8, b9 = (c.to_num(roster[v]) for v in ("b7", "b8", "b9"))
    out = pd.Series(pd.NA, index=roster.index, dtype="Int8")
    out[(b7 == NO) | (b8 == 0) | ((b8 == 1) & b9.between(10, 15))] = 0
    out[((b8 == 1) & (b9 == 16)) | b8.isin([2, 3, 4, 5])] = 1
    return out


def grade_number(code: pd.Series) -> pd.Series:
    """B12 grade code -> years of formal schooling: nursery 0, Primary 1-6 -> 1-6,
    JSS 1-3 -> 7-9, SS 1-3 -> 10-12, tertiary -> 13."""
    g = c.to_num(code)
    out = pd.Series(np.nan, index=code.index, dtype="float64")
    out[g.between(1, 3)] = 0
    out[g.between(11, 16)] = g - 10
    out[g.between(21, 26)] = g - 14
    out[g.between(31, 36)] = 13
    return out


def lagging(roster: pd.DataFrame) -> pd.Series:
    """For a child attending formal school: 1 if two or more grades behind the grade for age.

    Expected grade at age a is a - 5 (Primary 1 at the entry age 6), so lagging means
    grade <= a - 7. Higher education is never lagging; an unknown grade -> missing.
    Only children :func:`attending` (formal school) are assessed.
    """
    age = c.to_num(roster["b4a"])
    grade = grade_number(roster["b12"])
    level = c.to_num(roster["b11"])
    grade = grade.where(level != 3, 13)
    expected = age - (PRIMARY_ENTRY_AGE - 1)
    return _flag(expected - grade >= LAG_YEARS, grade.notna())


def education(roster: pd.DataFrame, households: pd.Index) -> pd.DataFrame:
    age = c.to_num(roster["b4a"])
    out = pd.DataFrame(index=households)
    school_age = roster[age.between(*ATTENDANCE_AGES)]
    out["school_attendance"] = household_any(
        school_age["hh_id"], 1 - c.to_num(attending(school_age)), households
    )
    adults = roster[age >= SCHOOLING_AGE]
    out["years_of_schooling"] = household_none_achieved(
        adults["hh_id"], completed_primary(adults), households
    )
    lag_age = roster[age.between(*LAG_AGES)]
    pupils = lag_age[attending(lag_age) == 1]
    out["school_lag"] = household_any(pupils["hh_id"], lagging(pupils), households)
    return out


# --- living standards ---------------------------------------------------------------


def water(i: pd.DataFrame) -> pd.Series:
    source = c.to_num(i["i1"])
    return _flag(source.isin(list(UNIMPROVED_WATER)), source.notna())


def water_reliability(i: pd.DataFrame) -> pd.Series:
    """Deprived if water is not regularly available (``i2`` = no) or is available fewer
    than 20 days a month or 4 hours a day. ``i2`` is asked only for some sources; where
    it is skipped by routing (unprotected wells and springs, tanker, cart, surface
    water) the household is non-deprived here (it is deprived in ``water``)."""
    source, regular = c.to_num(i["i1"]), c.to_num(i["i2"])
    hours, days = c.to_num(i["i2a"]), c.to_num(i["i2b"])
    short = (regular == NO) | ((regular == YES) & ((days < WATER_DAYS) | (hours < WATER_HOURS)))
    known = regular.isin([YES, NO]) | (source.notna() & regular.isna())
    return _flag(short, known)


def sanitation(i: pd.DataFrame) -> pd.Series:
    facility, shared = c.to_num(i["i4"]), c.to_num(i["i5"])
    return _flag(facility.isin(list(UNIMPROVED_SANITATION)) | (shared == SHARED), facility.notna())


def housing(j: pd.DataFrame) -> pd.Series:
    """Natural or rudimentary floor, roof or wall ("other" counts as not rudimentary)."""
    parts = [(j["j1"], RUDIMENTARY_FLOOR), (j["j2"], RUDIMENTARY_ROOF), (j["j3"], RUDIMENTARY_WALL)]
    bad = pd.concat([_in(v, codes) for v, codes in parts], axis=1).any(axis=1)
    known = pd.concat([c.to_num(v).notna() for v, _ in parts], axis=1).all(axis=1)
    return _flag(bad, known | bad)


def cooking_fuel(j: pd.DataFrame, codes: set[int] = SOLID_FUEL) -> pd.Series:
    fuel = c.to_num(j["j4"])
    return _flag(fuel.isin(list(codes)), fuel.notna())


def assets(k: pd.DataFrame) -> pd.Series:
    """Fewer than two of the listed assets and no car (missing items could be owned)."""
    items = [k[cols].apply(c.to_num) for cols in ASSET_ITEMS.values()]
    owned = pd.concat([(x == YES).any(axis=1) for x in items], axis=1).sum(axis=1)
    unknown = pd.concat(
        [~(x == YES).any(axis=1) & x.isna().any(axis=1) for x in items], axis=1
    ).sum(axis=1)
    car = c.to_num(k[CAR])
    deprived = (owned + unknown < 2) & (car == NO)
    return _flag(deprived, (owned >= 2) | (car == YES) | ((unknown == 0) & (car == NO)))


# --- work and shocks ----------------------------------------------------------------


def unemployed(work: pd.DataFrame) -> pd.Series:
    """Not in employment (``c0`` = 0), looking for work and available: 1/0/missing."""
    c0, looking, available = (c.to_num(work[v]) for v in ("c0", "c6", "c7"))
    known = (c0 == 1) | ((c0 == 0) & looking.isin([YES, NO]) & available.isin([YES, NO]))
    known = known | ((c0 == 0) & ((looking == NO) | (available == NO)))
    return _flag((c0 == 0) & (looking == YES) & (available == YES), known)


def underemployed(work: pd.DataFrame) -> pd.Series:
    """Employed, under 40 hours a week, willing (``c10``) and available (``c11``) for more."""
    c0, hours = c.to_num(work["c0"]), c.to_num(work["c9"])
    willing, available = c.to_num(work["c10"]), c.to_num(work["c11"])
    short = (c0 == 1) & (hours < WORK_HOURS)
    yes = short & (willing == YES) & (available == YES)
    known = (c0 == 0) | ((c0 == 1) & (hours >= WORK_HOURS)) | (short & (willing == NO))
    known = known | (short & willing.eq(YES) & available.isin([YES, NO]))
    return _flag(yes, known)


def work(c_frame: pd.DataFrame, roster: pd.DataFrame, households: pd.Index) -> pd.DataFrame:
    """Section C covers members 15+; members 15+ missing from it count as missing."""
    age = c.to_num(roster["b4a"])
    adults = roster.loc[age >= WORK_AGE, ["hh_id", "b1"]]
    people = adults.merge(
        c_frame, left_on=["hh_id", "b1"], right_on=["hh_id", "c00"], how="left",
        validate="one_to_one",
    )  # fmt: skip
    out = pd.DataFrame(index=households)
    out["unemployment"] = household_any(people["hh_id"], unemployed(people), households)
    out["underemployment"] = household_any(people["hh_id"], underemployed(people), households)
    return out


def security_shock(h2: pd.DataFrame) -> pd.Series:
    """Any of the eight incidents (footnote 12) in the past 12 months; 3 = don't know."""
    answers = h2[SHOCKS].apply(c.to_num)
    any_yes = (answers == YES).any(axis=1)
    all_no = (answers == NO).all(axis=1)
    return _flag(any_yes, all_no)


def security_shock_dk_not_deprived(h2: pd.DataFrame) -> pd.Series:
    """Outcome robustness (b): as :func:`security_shock`, but "don't know" counts as no."""
    answers = h2[SHOCKS].apply(c.to_num)
    any_yes = (answers == YES).any(axis=1)
    all_answered = answers.isin([NO, DONT_KNOW]).all(axis=1)
    return _flag(any_yes, all_answered)


# --- score, confounders, national figures -------------------------------------------


def score_points(deprivations: pd.DataFrame) -> pd.Series:
    """Weighted deprivation score in 480ths (exact); missing if any indicator is missing."""
    points = {k: int(w * POINTS) for k, w in WEIGHTS.items()}
    frame = deprivations[INDICATORS].astype("Int16")
    total = sum(frame[k] * p for k, p in points.items())
    return pd.Series(total, index=deprivations.index, dtype="Int16")


def is_poor(points: pd.Series, k: Fraction = K) -> pd.Series:
    """Poor if score >= k (both exact)."""
    cutoff = k * POINTS
    return (points.astype("Float64") >= float(cutoff)).astype("Int8")


def head_education(roster: pd.DataFrame) -> pd.Series:
    b7, b8 = c.to_num(roster["b7"]), c.to_num(roster["b8"])
    done = completed_primary(roster)
    out = pd.Series(pd.NA, index=roster.index, dtype="string")
    out[b8 == 0] = "preschool"
    out[b8 == 4] = "non_formal"
    out[(b8 == 1) & (done == 0)] = "primary_incomplete"
    out[(b8 == 1) & (done == 1)] = "primary"
    out[b8.isin([2, 5])] = "secondary"
    out[b8 == 3] = "higher"
    out[b7 == NO] = "none"
    return out


def household_structure(roster: pd.DataFrame, households: pd.Index) -> pd.DataFrame:
    """Member counts by age band and the head's sex, age and education.

    The head is ``b5 == 1``. Households with several heads use the lowest line number
    (``n_heads`` records how many); households with none have the head fields missing.
    """
    age = c.to_num(roster["b4a"])
    out = pd.DataFrame(index=households)
    for column, (lo, hi) in {**AGE_COUNTS, **P5_AGE_COUNTS}.items():
        in_band = roster.loc[age.between(lo, hi), "hh_id"]
        out[column] = in_band.value_counts().reindex(households).fillna(0).astype("Int16")
    heads = roster[c.to_num(roster["b5"]) == HEAD]
    out["n_heads"] = heads["hh_id"].value_counts().reindex(households).fillna(0).astype("Int8")
    first = heads.assign(_line=c.to_num(heads["b1"])).sort_values(["hh_id", "_line"])
    first = first.drop_duplicates("hh_id").set_index("hh_id").reindex(households)
    out["head_sex"] = c.recode(first["b3"], c.SEX)
    out["head_age"] = c.to_num(first["b4a"]).astype("Int16")
    out["head_education"] = head_education(first)
    return out


def build(
    sections: Mapping[str, pd.DataFrame],
    tables: who_growth.Tables,
    state_labels: dict[int, str],
    lookup: StateLookup,
) -> pd.DataFrame:
    """Household frame: design, weights, confounders, 15 deprivations, score and poverty.

    Households without a positive ``pop_wgt`` (not interviewed) are dropped.
    """
    a = sections[SECTION_A]
    a = a[c.to_num(a["pop_wgt"]) > 0].drop_duplicates("hh_id")
    households = pd.Index(a["hh_id"], name="hh_id")
    roster = sections[SECTION_B]
    roster = roster[roster["hh_id"].isin(households)]
    a = a.set_index("hh_id")

    out = pd.DataFrame(index=households)
    out["source"] = SOURCE
    c.attach_state(out, a["a1"], lookup.map_codes(state_labels))
    out["senatorial_district"] = c.code_text(a["a1b"])
    out["sector"] = c.recode(a["a3"], c.SECTOR)
    out["stratum"] = c.join_codes(SOURCE, a["a1"], a["a1b"], a["a3"])
    out["psu"] = c.join_codes(SOURCE, a["a4"])
    out["hhsize"] = c.to_num(a["hhsize"]).astype("Int16")
    out["hh_wgt"] = c.to_num(a["hh_wgt"])
    out["pop_wgt"] = c.to_num(a["pop_wgt"])
    out["person_weight"] = out["pop_wgt"] / out["hhsize"].astype("float64")
    if SECTION_Q in sections:
        q = _by_household(sections[SECTION_Q], households)
        out["a9a"] = c.to_num(q["a9a"]).astype("Int8")
    else:
        out["a9a"] = pd.Series(pd.NA, index=households, dtype="Int8")
    out = out.join(household_structure(roster, households))

    kids = child_undernourished(sections[SECTION_T], roster, tables)
    adults = adult_underweight(sections[SECTION_R])
    dep = pd.DataFrame(index=households)
    dep["nutrition"] = nutrition(kids, adults, households)
    dep["food_insecurity"] = food_insecurity(_by_household(sections[SECTION_E], households))
    dep["time_to_healthcare"] = time_to_healthcare(_by_household(sections[SECTION_F], households))
    dep = dep.join(education(roster, households))
    i = _by_household(sections[SECTION_I], households)
    j = _by_household(sections[SECTION_J], households)
    dep["water"] = water(i)
    dep["water_reliability"] = water_reliability(i)
    dep["sanitation"] = sanitation(i)
    dep["housing"] = housing(j)
    dep["cooking_fuel"] = cooking_fuel(j)
    dep["assets"] = assets(_by_household(sections[SECTION_K], households))
    dep = dep.join(work(sections[SECTION_C], roster, households))
    dep["security_shock"] = security_shock(_by_household(sections[SECTION_H2], households))
    dep = dep[INDICATORS].astype("Int8")

    out = out.join(dep.add_prefix("d_"))
    out["n_missing"] = dep.isna().sum(axis=1).astype("Int8")
    points = score_points(dep)
    out["score"] = points.astype("Float64") / POINTS
    out["poor"] = is_poor(points)
    # Outcome robustness (pre-registration 3.3): one indicator swapped, the rest unchanged.
    alternatives = {
        # suffix: (indicator swapped, its alternative column, values)
        "fuel_alt": ("cooking_fuel", "d_cooking_fuel_alt", cooking_fuel(j, SOLID_FUEL_NO_CHARCOAL)),
        "shock_dk0": (
            "security_shock",
            "d_security_shock_dk0",
            security_shock_dk_not_deprived(_by_household(sections[SECTION_H2], households)),
        ),
    }
    for name, (indicator, column, values) in alternatives.items():
        swapped = dep.copy()
        swapped[indicator] = values.astype("Int8")
        out[column] = swapped[indicator]
        alt_points = score_points(swapped)
        out[f"score_{name}"] = alt_points.astype("Float64") / POINTS
        out[f"poor_{name}"] = is_poor(alt_points)
    out.index = c.code_text(pd.Series(out.index, index=out.index)).to_numpy()
    out.index.name = "hh_id"
    return out.reset_index()


@dataclass(frozen=True)
class National:
    """National figures over households with all 15 indicators (% of people)."""

    households: int
    households_used: int
    headline: dict[str, float]
    """H (%), A (%), MPI."""
    uncensored: dict[str, float]
    censored: dict[str, float]


def national(frame: pd.DataFrame, weight: str = "pop_wgt") -> National:
    """H, A, MPI and each indicator's uncensored and censored headcount (% of people),
    over households with all 15 indicators, each weighted by ``weight``."""
    full = frame[frame["poor"].notna()]
    w = full[weight].astype("float64")
    poor = full["poor"].astype("float64")
    score = full["score"].astype("float64")
    h = float((w * poor).sum() / w.sum())
    a = float((w * poor * score).sum() / (w * poor).sum())
    uncensored, censored = {}, {}
    for k in INDICATORS:
        d = full[f"d_{k}"].astype("float64")
        uncensored[k] = float(100 * (w * d).sum() / w.sum())
        censored[k] = float(100 * (w * d * poor).sum() / w.sum())
    return National(
        households=len(frame),
        households_used=len(full),
        headline={"H": 100 * h, "A": 100 * a, "MPI": h * a},
        uncensored=uncensored,
        censored=censored,
    )


def within_tolerance(result: National) -> dict[str, bool]:
    return {k: abs(result.headline[k] - PUBLISHED[k]) <= TOLERANCE[k] for k in PUBLISHED}


def report(result: National) -> bool:
    c.log(
        f"  households interviewed: {c.masked(result.households)}; "
        f"with all 15 indicators: {c.masked(result.households_used)}"
    )
    checks = within_tolerance(result)
    c.log("  national (people, k = 26%)   rebuilt  published  tolerance  result")
    for k, fmt in (("H", "{:.1f}"), ("A", "{:.1f}"), ("MPI", "{:.3f}")):
        c.log(
            f"  {k:<28} {fmt.format(result.headline[k]):>7}  {fmt.format(PUBLISHED[k]):>9}  "
            f"{'+/-' + str(TOLERANCE[k]):>9}  {'PASS' if checks[k] else 'FAIL'}"
        )
    c.log("  indicator             uncensored (D2)       censored (D3)")
    for k in INDICATORS:
        c.log(
            f"  {k:<20} {result.uncensored[k]:5.1f} vs {PUBLISHED_UNCENSORED[k]:5.1f}"
            f"   {result.censored[k]:5.1f} vs {PUBLISHED_CENSORED[k]:5.1f}"
        )
    passed = all(checks.values())
    c.log(f"validation: {'PASS' if passed else 'FAIL'} (tolerance fixed before the run)")
    return passed


def read_sections(data_dir: Path) -> tuple[dict[str, pd.DataFrame], dict[int, str]]:
    sections: dict[str, pd.DataFrame] = {}
    labels: dict[int, str] = {}
    for name, columns in COLUMNS.items():
        frame, meta = c.read_dta(data_dir / name, columns)
        sections[name] = frame
        if name == SECTION_A:
            labels = c.value_labels(meta, "a1")
    return sections, labels


@c.safe_main
def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Rebuild the MPI 2021 at household level.")
    parser.add_argument("--data-dir", type=Path, default=DATA_DIR)
    parser.add_argument("--out-dir", type=Path, default=c.DERIVED)
    parser.add_argument("--who-dir", type=Path, default=who_growth.WHO_DIR)
    parser.add_argument(
        "--validate", action="store_true", help="compare national figures with the report"
    )
    args = parser.parse_args(argv)

    c.log("MPI 2021 poverty: reading Sections A, B, C, E, F, H2, I, J, K, Q, R, T (not D)")
    sections, labels = read_sections(args.data_dir)
    tables = who_growth.load_tables(args.who_dir)
    frame = build(sections, tables, labels, StateLookup.from_seeds())
    c.report_counts("heads per household", frame["n_heads"])
    for k in INDICATORS:
        c.log(f"  {k}: missing in {c.masked(int(frame[f'd_{k}'].isna().sum()))} households")
    args.out_dir.mkdir(parents=True, exist_ok=True)
    path = args.out_dir / f"{NAME}.parquet"
    frame.to_parquet(path, index=False, compression="zstd")
    shown = path.relative_to(c.ROOT).as_posix() if path.is_relative_to(c.ROOT) else path.name
    c.log(f"wrote {c.masked(len(frame))} household rows to {shown}")
    if args.validate:
        return 0 if report(national(frame)) else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
