"""Harmonise NBS MPI 2021 Section D (disability, members 5+) to the common schema.

MPI 2021's module is **not** the Washington Group Short Set (``docs/verification.md`` D39,
D43), so no ``disability3`` is computed. Per domain:

* seeing ``d2``, hearing ``d3a``, walking ``d5`` are yes/no screeners. The 1-4 severity
  question (``d2b``, ``d4b``, ``d8``: "even when wearing glasses / using a hearing aid /
  using equipment") was asked only when the screener was "yes" **and** the person uses the
  aid (``d2a``, ``d3b``, ``d6a``). So each gets ``mpi_<domain>_screener`` (1 yes, 0 no) and
  ``mpi_<domain>_severity`` (1-4, aid users only; anything outside that route is set to
  missing).
* communication is two items, ``d9a`` understanding and ``d10a`` being understood; the
  domain is the worse of the two (:func:`common.worse_of`).
* self-care ``d11a``, cognition ``d12a``: the 1-4 scale as asked.
* upper body: the worse of ``d13a`` (raising a 2-litre bottle) and ``d14a`` (hands and
  fingers), as in the WG-SS Enhanced upper-body domain.

Code 5 ("don't know / refused") is missing throughout.

Design (assumption, ``verification.md`` D40): no strata variable is shipped, so strata =
state ``a1`` x senatorial district ``a1b`` x sector ``a3`` (state is included so the
strata are right whether or not ``a1b`` codes are unique nationally), PSU = EA ``a4``
(nested in strata in R).
Person weight = ``pop_wgt / hhsize``: ``pop_wgt`` equals ``hh_wgt x hhsize`` times one
calibration factor per state (checked from the data), so this is the household weight,
calibrated to the state population. Households without a weight are dropped.
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

import pandas as pd

from curbcut_ingest.restricted import common as c
from curbcut_ingest.states import StateLookup

SOURCE = "mpi2021"
DATA_DIR = c.RESTRICTED / "nbs-mpi-2021" / "_data"
SECTION_A = "SECTION A _ IDENTIFICATION.dta"
SECTION_B = "SECTION B-DEMOGRAPHIC CHARACTERISTIC.dta"
SECTION_D = "SECTION D_ DISABILITY FOR 5 YEARS AND ABOVE.dta"

A_COLUMNS = ["hh_id", "a1", "a1b", "a3", "a4", "pop_wgt", "hhsize"]
B_COLUMNS = ["hh_id", "b1", "b3", "b4a"]
SCREENED = {
    # domain: (screener, aid use, severity "even when using the aid")
    "seeing": ("d2", "d2a", "d2b"),
    "hearing": ("d3a", "d3b", "d4b"),
    "walking": ("d5", "d6a", "d8"),
}
SCALED = ["d9a", "d10a", "d11a", "d12a", "d13a", "d14a"]
D_COLUMNS = ["hh_id", "d1", *(v for t in SCREENED.values() for v in t), *SCALED]

MPI_COLUMNS = [
    *(f"mpi_{d}_{part}" for d in SCREENED for part in ("screener", "aid", "severity")),
    "mpi_communication",
    "mpi_selfcare",
    "mpi_cognition",
    "mpi_upper_body",
]

YES, NO = 1, 2


def yes_no(values: pd.Series) -> pd.Series:
    numeric = c.to_num(values)
    out = pd.Series(pd.NA, index=values.index, dtype="Int8")
    out[numeric == YES] = 1
    out[numeric == NO] = 0
    return out


def routed_severity(screener: pd.Series, aid: pd.Series, severity: pd.Series) -> pd.Series:
    """Severity is kept only on its route (screener yes and aid yes); else missing."""
    on_route = (yes_no(screener) == 1) & (yes_no(aid) == 1)
    return c.wg_scale(severity).where(on_route.fillna(False).astype(bool)).astype("Int8")


def harmonise_disability(d: pd.DataFrame) -> pd.DataFrame:
    """Section D codes -> MPI's own per-domain measures. Pure; tested on invented rows."""
    out = pd.DataFrame(index=d.index)
    for domain, (screener, aid, severity) in SCREENED.items():
        out[f"mpi_{domain}_screener"] = yes_no(d[screener])
        # Aid use is only meaningful after a "yes" screener.
        out[f"mpi_{domain}_aid"] = yes_no(d[aid]).where(out[f"mpi_{domain}_screener"] == 1)
        out[f"mpi_{domain}_severity"] = routed_severity(d[screener], d[aid], d[severity])
    out["mpi_communication"] = c.worse_of(c.wg_scale(d["d9a"]), c.wg_scale(d["d10a"]))
    out["mpi_selfcare"] = c.wg_scale(d["d11a"])
    out["mpi_cognition"] = c.wg_scale(d["d12a"])
    out["mpi_upper_body"] = c.worse_of(c.wg_scale(d["d13a"]), c.wg_scale(d["d14a"]))
    return out


def off_route_answers(d: pd.DataFrame) -> dict[str, int]:
    """Count severity answers given off their route (expected 0; D43)."""
    counts = {}
    for domain, (screener, aid, severity) in SCREENED.items():
        on_route = (yes_no(d[screener]) == 1) & (yes_no(d[aid]) == 1)
        answered = c.wg_scale(d[severity]).notna()
        counts[domain] = int((answered & ~on_route.fillna(False).astype(bool)).sum())
    return counts


def harmonise(
    a: pd.DataFrame,
    b: pd.DataFrame,
    d: pd.DataFrame,
    state_labels: dict[int, str],
    lookup: StateLookup,
) -> pd.DataFrame:
    states = lookup.map_codes(state_labels)
    people = d.merge(
        b, left_on=["hh_id", "d1"], right_on=["hh_id", "b1"], how="inner", validate="many_to_one"
    )
    people = people.merge(a, on="hh_id", how="inner", validate="many_to_one")
    weight = c.to_num(people["pop_wgt"]) / c.to_num(people["hhsize"])
    age = c.to_num(people["b4a"])

    out = pd.DataFrame(index=people.index)
    out["source"] = SOURCE
    out["person_id"] = c.join_codes(SOURCE, people["hh_id"], people["d1"])
    c.attach_state(out, people["a1"], states)
    out["sector"] = c.recode(people["a3"], c.SECTOR)
    out["sex"] = c.recode(people["b3"], c.SEX)
    out["age"] = age.astype("Int16")
    out["age_group"] = c.age_group(age)
    out["age_band"] = c.age_band(age)
    out["weight"] = weight
    out["stratum"] = c.join_codes(SOURCE, people["a1"], people["a1b"], people["a3"])
    out["psu"] = c.join_codes(SOURCE, people["a4"])
    out = pd.concat([out, harmonise_disability(people)], axis=1)
    keep = weight.notna() & (weight > 0) & (age >= 5)
    return c.finish(out[keep], MPI_COLUMNS)


@c.safe_main
def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Harmonise MPI 2021 to person-level Parquet.")
    parser.add_argument("--data-dir", type=Path, default=DATA_DIR)
    parser.add_argument("--out-dir", type=Path, default=c.DERIVED)
    args = parser.parse_args(argv)

    c.log("MPI 2021: reading Sections A, B and D (named columns only)")
    a, meta_a = c.read_dta(args.data_dir / SECTION_A, A_COLUMNS)
    b, _ = c.read_dta(args.data_dir / SECTION_B, B_COLUMNS)
    d, _ = c.read_dta(args.data_dir / SECTION_D, D_COLUMNS)
    c.log(f"  Section D rows: {c.masked(len(d))}")
    matched_b = d.merge(b, left_on=["hh_id", "d1"], right_on=["hh_id", "b1"]).shape[0]
    c.report_match("D to B on (hh_id, d1 = b1)", int(matched_b), len(d))
    c.report_match("D to A on hh_id", int(d["hh_id"].isin(a["hh_id"]).sum()), len(d))
    for domain, n in off_route_answers(d).items():
        c.log(f"  {domain}: severity answers off route (set missing): {c.masked(n)}")
    frame = harmonise(a, b, d, c.value_labels(meta_a, "a1"), StateLookup.from_seeds())
    c.log(f"  people with a weight, aged 5+: {c.masked(len(frame))}")
    c.report_counts("age_group", frame["age_group"])
    c.write_parquet(frame, SOURCE, args.out_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
