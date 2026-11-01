"""P5 exposure: households with a member who has a severe functional difficulty (MPI 2021).

Implements ``docs/preregistration.md`` section 3.2 and the exposure definitions of S2, S3,
S5 and S6, from MPI 2021 Section D (members 5+) and the roster ages (Section B). **No
poverty, deprivation or work variable is read here**: this is the "before registration"
step of section 5.6, and its output has no outcome column.

Per person and domain, a status of 1 (severe), 0 (not severe) or missing:

* self-care ``d11a``, remembering ``d12a``: severe at "a lot of difficulty" (3) or
  "cannot do at all" (4);
* communication: the worse of ``d9a`` and ``d10a`` (:func:`common.worse_of`);
* seeing, hearing, walking (:func:`screened_status`): screener "no" -> 0; screener "yes"
  and aid "yes" -> the severity answer "even when using the aid" at the definition's
  threshold (missing if not given); screener "yes" and aid "no" -> **no severity answer**
  (D43): the definition's ``unasked`` status (0 in the primary definition, 1 in S2 and
  S5). Anything else (screener or aid missing) -> missing.

A household is **exposed** if any member 5+ has a status of 1 in any domain, whatever the
other members' missing answers (author's decision of 2026-10-31). Otherwise it is
**unexposed** if every member 5+ has a non-missing, not-severe status in every domain;
**excluded** if a member's statuses are all missing (including a roster member 5+ with no
Section D record); and missing if a member's statuses are partly missing. Each household's
reason is kept.

Definitions (``DEFINITIONS``):

* ``primary``: section 3.2 (six domains, screened domains as above).
* ``s2`` (NBS's broad definition, Table 7 footnote 19: "some difficulty, a lot of
  difficulty or complete difficulty ... even when using equipment or being assisted"):
  "some difficulty" or worse (2+) in any item, including the upper-body items (``d13a``
  lifting, ``d14a`` hands) and the skin item ``d15a`` (albinism, vitiligo; asked on the same
  1-4 scale). Seeing, hearing and walking ("reading C", author's decision of 2026-10-31):
  an aid user counts at 2+ on the "even when using the aid" item; a "yes" screener without
  an aid counts as a difficulty (without an aid, the difficulty with one is the difficulty
  without); a "no" screener is 0.
* ``s3``: the household head (``b5`` = 1, lowest line if several) is severe (primary rule);
  unexposed if the head's answers are complete and not severe; else missing.
* ``s5``: as primary, with screener "yes" and no aid counted as severe.
* ``s6``: routing-free: self-care, remembering and communication only.

Output: ``data/restricted/derived/mpi2021_exposure.parquet`` (git-ignored): ``hh_id``, the
sample flag, the number of members 5+, and per definition ``exposed_<def>`` (1/0/missing)
and ``reason_<def>``. ``--check`` prints the section 5.6 check: the weighted share of
people in exposed households under each definition (``pop_wgt``), with S2 against NBS's
11.0% (+/- 1.5 points).
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from curbcut_ingest.restricted import common as c
from curbcut_ingest.restricted.mpi2021 import (
    DATA_DIR,
    SCREENED,
    SECTION_A,
    SECTION_B,
    SECTION_D,
    yes_no,
)

NAME = "mpi2021_exposure"
SECTION_Q = "SECTION Q_HOUSEHOLD RESPONSE STATUS.dta"
A_COLUMNS = ["hh_id", "pop_wgt"]
B_COLUMNS = ["hh_id", "b1", "b4a", "b5"]
D_COLUMNS = [
    "hh_id",
    "d1",
    *(v for t in SCREENED.values() for v in t),
    "d9a",
    "d10a",
    "d11a",
    "d12a",
    "d13a",
    "d14a",
    "d15a",
]
Q_COLUMNS = ["hh_id", "a9a"]

MIN_AGE = 5
HEAD = 1
COMPLETED = 1
SEVERE = 3
SOME = 2
DEFINITIONS = ("primary", "s2", "s3", "s5", "s6")
SCALED_DOMAINS = ("selfcare", "cognition", "communication")
PRIMARY_DOMAINS = (*SCREENED, *SCALED_DOMAINS)

NBS_SHARE = 11.0
"""NBS Table 7 (D61): % of the population in households with a person living with a
disability (broad definition)."""
NBS_TOLERANCE = 1.5
"""Percentage points; fixed in the pre-registration (section 5.6)."""

# Reasons a household's exposure is missing (or why it is out of the sample).
EXPOSED, UNEXPOSED = "exposed", "unexposed"
MEMBER_ALL_MISSING = "excluded: member with all answers missing, no one severe"
MEMBER_PART_MISSING = "missing: member with some answers missing, no one severe"
HEAD_MISSING = "missing: no head, or head's answers incomplete"


# --- per person ----------------------------------------------------------------------


def screened_status(
    screener: pd.Series,
    aid: pd.Series,
    severity: pd.Series,
    unasked: int,
    threshold: int = SEVERE,
) -> pd.Series:
    """Status (1/0/missing) for a screened domain.

    An aid user's status is 1 if the "even when using the aid" answer is at ``threshold``
    or worse (3, severe, by default; 2 in S2). ``unasked`` is the status given to
    "screener yes, no aid" (no severity was asked): 0 in the primary definition, 1 in S2
    and S5.
    """
    scr, uses = yes_no(screener), yes_no(aid)
    level = c.wg_scale(severity)
    out = pd.Series(pd.NA, index=screener.index, dtype="Int8")
    out[(scr == 0).fillna(False).astype(bool)] = 0
    on_route = ((scr == 1) & (uses == 1)).fillna(False).astype(bool)
    rated = on_route & level.notna()
    out[rated] = (level[rated] >= threshold).astype("Int8")
    off_route = ((scr == 1) & (uses == 0)).fillna(False).astype(bool)
    out[off_route] = unasked
    return out


def scaled_status(level: pd.Series, cut: int = SEVERE) -> pd.Series:
    """1 if level >= cut, 0 if answered below it, missing otherwise."""
    out = pd.Series(pd.NA, index=level.index, dtype="Int8")
    known = level.notna()
    out[known] = (level[known] >= cut).astype("Int8")
    return out


def person_domains(d: pd.DataFrame, definition: str) -> pd.DataFrame:
    """Per person, one 1/0/missing status column per domain counted by ``definition``.

    ``s3`` uses the primary domains (it differs only in whose answers count).
    """
    out = pd.DataFrame(index=d.index)
    scaled = {
        "selfcare": c.wg_scale(d["d11a"]),
        "cognition": c.wg_scale(d["d12a"]),
        "communication": c.worse_of(c.wg_scale(d["d9a"]), c.wg_scale(d["d10a"])),
    }
    if definition == "s6":
        for name, level in scaled.items():
            out[name] = scaled_status(level)
        return out
    if definition == "s2":
        for domain, (screener, aid, severity) in SCREENED.items():
            out[domain] = screened_status(d[screener], d[aid], d[severity], 1, SOME)
        for name, item in {
            "understanding": "d9a",
            "being_understood": "d10a",
            "selfcare": "d11a",
            "cognition": "d12a",
            "lifting": "d13a",
            "hands": "d14a",
            "skin": "d15a",
        }.items():
            out[name] = scaled_status(c.wg_scale(d[item]), SOME)
        return out
    unasked = 1 if definition == "s5" else 0
    for domain, (screener, aid, severity) in SCREENED.items():
        out[domain] = screened_status(d[screener], d[aid], d[severity], unasked)
    for name, level in scaled.items():
        out[name] = scaled_status(level)
    return out


def person_status(domains: pd.DataFrame) -> pd.DataFrame:
    """severe (any domain 1), complete (every domain known), all_missing (none known)."""
    known = domains.notna()
    return pd.DataFrame(
        {
            "severe": (domains == 1).fillna(False).any(axis=1),
            "complete": known.all(axis=1),
            "all_missing": ~known.any(axis=1),
        },
        index=domains.index,
    )


# --- per household -------------------------------------------------------------------


@dataclass(frozen=True)
class Members:
    """Members aged 5+ of each household: their Section D answers (or none) and role."""

    frame: pd.DataFrame
    """One row per member 5+: ``hh_id``, ``line``, ``is_head``, ``in_d`` and the D items."""
    dropped_under5_in_d: int
    """Section D records whose roster age is under 5 (not assessed; dropped)."""


def members_5plus(b: pd.DataFrame, d: pd.DataFrame) -> Members:
    """Members aged 5+: the roster's members 5+ plus Section D records whose roster age is
    unknown (they were assessed, so they count). D records with a roster age under 5 are
    dropped and counted. A roster member 5+ with no D record has all answers missing."""
    roster = b.assign(line=c.to_num(b["b1"]), age=c.to_num(b["b4a"]))[
        ["hh_id", "line", "age", "b5"]
    ]
    dd = d.assign(line=c.to_num(d["d1"])).drop(columns="d1")
    merged = roster.merge(
        dd, on=["hh_id", "line"], how="outer", indicator=True, validate="one_to_one"
    )
    merged["in_d"] = merged["_merge"] != "left_only"
    under5 = merged["age"] < MIN_AGE
    dropped = int((under5 & merged["in_d"]).sum())
    keep = (merged["age"] >= MIN_AGE) | (merged["age"].isna() & merged["in_d"])
    out = merged[keep].drop(columns="_merge").copy()
    # The head: b5 == 1, the lowest line number if several (as in mpi2021_poverty).
    heads = out[c.to_num(out["b5"]) == HEAD].sort_values(["hh_id", "line"])
    first = heads.drop_duplicates("hh_id")
    out["is_head"] = False
    out.loc[first.index, "is_head"] = True
    return Members(out.reset_index(drop=True), dropped)


def household_exposure(members: pd.DataFrame, definition: str) -> pd.DataFrame:
    """Per household with at least one member 5+: ``exposed`` (1/0/missing) and ``reason``."""
    domains = person_domains(members, definition)
    # A member 5+ with no Section D record has every status missing already (NaN items).
    status = person_status(domains)
    status["hh_id"] = members["hh_id"].to_numpy()
    status["is_head"] = members["is_head"].to_numpy()
    households = pd.Index(pd.unique(members["hh_id"]), name="hh_id")
    out = pd.DataFrame(index=households)

    if definition == "s3":
        head = status[status["is_head"]].set_index("hh_id").reindex(households)
        severe = head["severe"].fillna(False).astype(bool)
        complete = head["complete"].fillna(False).astype(bool)
        out["exposed"] = pd.Series(pd.NA, index=households, dtype="Int8")
        out.loc[complete, "exposed"] = 0
        out.loc[severe, "exposed"] = 1
        out["reason"] = np.where(severe, EXPOSED, np.where(complete, UNEXPOSED, HEAD_MISSING))
        return out

    grouped = status.groupby("hh_id", sort=False)
    any_severe = grouped["severe"].any().reindex(households)
    all_complete = grouped["complete"].all().reindex(households)
    any_all_missing = grouped["all_missing"].any().reindex(households)
    exposed = pd.Series(pd.NA, index=households, dtype="Int8")
    exposed[all_complete & ~any_severe] = 0
    # A severe member makes the household exposed whatever the others' missing answers
    # (author's decision of 2026-10-31); only would-be unexposed households are excluded.
    exposed[any_severe] = 1
    reason = np.where(
        any_severe,
        EXPOSED,
        np.where(
            any_all_missing,
            MEMBER_ALL_MISSING,
            np.where(all_complete, UNEXPOSED, MEMBER_PART_MISSING),
        ),
    )
    out["exposed"] = exposed
    out["reason"] = reason
    return out


def build(
    a: pd.DataFrame, b: pd.DataFrame, d: pd.DataFrame, q: pd.DataFrame
) -> tuple[pd.DataFrame, Members]:
    """Household exposure frame for every definition. Pure; tested on invented rows.

    ``in_sample``: completed interview (``a9a`` = 1), a positive ``pop_wgt`` and at least
    one member 5+ with a Section D record (section 3.1).
    """
    members = members_5plus(b, d)
    frame = members.frame
    with_d = frame.groupby("hh_id")["in_d"].any()
    households = pd.Index(sorted(set(a["hh_id"]) | set(frame["hh_id"])), name="hh_id")
    out = pd.DataFrame(index=households)
    sizes = frame.groupby("hh_id").size().reindex(households).fillna(0)
    out["n_members_5plus"] = sizes.astype("Int16")
    a_ = a.drop_duplicates("hh_id").set_index("hh_id").reindex(households)
    q_ = q.drop_duplicates("hh_id").set_index("hh_id").reindex(households)
    completed = c.to_num(q_["a9a"]) == COMPLETED
    weighted = c.to_num(a_["pop_wgt"]) > 0
    out["in_sample"] = (completed & weighted & with_d.reindex(households).fillna(False)).astype(
        bool
    )
    for definition in DEFINITIONS:
        hh = household_exposure(frame, definition).reindex(households)
        out[f"exposed_{definition}"] = hh["exposed"].astype("Int8")
        out[f"reason_{definition}"] = hh["reason"].astype("string")
    out.index = c.code_text(pd.Series(out.index, index=out.index)).to_numpy()
    out.index.name = "hh_id"
    return out.reset_index(), members


# --- the section 5.6 check -----------------------------------------------------------


@dataclass(frozen=True)
class Share:
    definition: str
    share: float
    """% of people (pop_wgt) in exposed households, among sample households with a known
    exposure under this definition."""
    households: int
    households_missing: int
    weighted_missing: float
    """% of the sample's people in households whose exposure is missing or excluded."""
    missing_by_reason: dict[str, tuple[str, float]] = field(default_factory=dict)
    """Per reason for a missing exposure: (households, masked; % of the sample's people)."""


def exposure_shares(frame: pd.DataFrame, weights: pd.Series) -> dict[str, Share]:
    """Weighted share of people in exposed households, per definition (sample only).

    ``weights`` is ``pop_wgt`` indexed like ``frame`` (household weight x size), so the
    share is a share of people, like NBS's 11.0%.
    """
    sample = frame["in_sample"].astype(bool)
    w = c.to_num(weights)[sample]
    out = {}
    for definition in DEFINITIONS:
        exposed = frame.loc[sample, f"exposed_{definition}"]
        known = exposed.notna()
        share = float((w[known] * exposed[known].astype("float64")).sum() / w[known].sum())
        reasons = frame.loc[sample, f"reason_{definition}"]
        by_reason = {}
        for r in sorted(reasons[~known].dropna().unique()):
            hit = ~known & (reasons == r)
            by_reason[str(r)] = (
                c.masked(int(hit.sum())),
                float(100 * w[hit].sum() / w.sum()),
            )
        out[definition] = Share(
            definition=definition,
            share=100 * share,
            households=int(known.sum()),
            households_missing=int((~known).sum()),
            weighted_missing=float(100 * w[~known].sum() / w.sum()),
            missing_by_reason=by_reason,
        )
    return out


def nbs_check(shares: Mapping[str, Share]) -> bool:
    return abs(shares["s2"].share - NBS_SHARE) <= NBS_TOLERANCE


def report(frame: pd.DataFrame, shares: Mapping[str, Share], members: Members) -> bool:
    c.log(
        f"  households: {c.masked(len(frame))}; "
        f"in the P5 sample: {c.masked(int(frame['in_sample'].sum()))}"
    )
    c.log(
        "  Section D records with a roster age under 5 (dropped): "
        f"{c.masked(members.dropped_under5_in_d)}"
    )
    no_d = int((~members.frame["in_d"]).sum())
    c.log(f"  roster members 5+ with no Section D record (all answers missing): {c.masked(no_d)}")
    sample = frame[frame["in_sample"]]
    for definition in DEFINITIONS:
        c.report_counts(f"{definition} reasons (sample households)", sample[f"reason_{definition}"])
    c.log(
        "  definition  % of people in exposed households  households used  missing (hh, % people)"
    )
    for definition, s in shares.items():
        c.log(
            f"  {definition:<10} {s.share:6.2f}  {c.masked(s.households):>15}  "
            f"{c.masked(s.households_missing):>8}, {s.weighted_missing:4.1f}%"
        )
    for definition, s in shares.items():
        parts = [f"{r}: {n} hh, {pct:.2f}%" for r, (n, pct) in s.missing_by_reason.items()]
        c.log(f"  {definition} missing by reason (% of people): " + ("; ".join(parts) or "none"))
    passed = nbs_check(shares)
    c.log(
        f"S2 vs NBS Table 7: {shares['s2'].share:.2f} vs {NBS_SHARE} (+/-{NBS_TOLERANCE}): "
        f"{'PASS' if passed else 'FAIL'}"
    )
    return passed


class OutDirError(ValueError):
    """Raised when an output folder lies outside the restricted zone."""


def restricted_out_dir(path: Path) -> Path:
    """``path`` resolved, if it lies under the git-ignored restricted folder
    (``common.RESTRICTED``, read at call time); otherwise :class:`OutDirError`. Outputs
    built from microdata never leave the restricted zone."""
    resolved, root = path.resolve(), c.RESTRICTED.resolve()
    if not resolved.is_relative_to(root):
        raise OutDirError("--out-dir must be under data/restricted/ (the restricted zone)")
    return resolved


def read(data_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    a, _ = c.read_dta(data_dir / SECTION_A, A_COLUMNS)
    b, _ = c.read_dta(data_dir / SECTION_B, B_COLUMNS)
    d, _ = c.read_dta(data_dir / SECTION_D, D_COLUMNS)
    q, _ = c.read_dta(data_dir / SECTION_Q, Q_COLUMNS)
    return a, b, d, q


@c.safe_main
def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build the P5 household exposure flags (MPI 2021)."
    )
    parser.add_argument("--data-dir", type=Path, default=DATA_DIR)
    parser.add_argument("--out-dir", type=Path, default=c.DERIVED)
    parser.add_argument(
        "--check",
        action="store_true",
        help="print the pre-registration 5.6 check (exposure shares only; no poverty data)",
    )
    args = parser.parse_args(argv)
    try:
        out_dir = restricted_out_dir(args.out_dir)
    except OutDirError as exc:
        c.log(f"refused: {exc}")
        return 2

    c.log("P5 exposure: reading Sections A (weights), B (ages, head), D (disability), Q (response)")
    a, b, d, q = read(args.data_dir)
    frame, members = build(a, b, d, q)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{NAME}.parquet"
    frame.to_parquet(path, index=False, compression="zstd")
    shown = path.relative_to(c.ROOT).as_posix() if path.is_relative_to(c.ROOT) else path.name
    c.log(f"wrote {c.masked(len(frame))} household rows to {shown}")
    if args.check:
        weights = a.drop_duplicates("hh_id").set_index(
            c.code_text(a.drop_duplicates("hh_id")["hh_id"])
        )["pop_wgt"]
        w = weights.reindex(frame["hh_id"].to_numpy())
        w.index = frame.index
        return 0 if report(frame, exposure_shares(frame, w), members) else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
