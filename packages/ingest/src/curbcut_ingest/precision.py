"""Precision flag for survey proportions: the NCHS Data Presentation Standards for Proportions.

Source: Parker JD, Talih M, Malec DJ, et al. National Center for Health Statistics data
presentation standards for proportions. Vital Health Stat 2(175), 2017 (revised 2018, 2021),
https://www.cdc.gov/nchs/data/series/sr_02/sr02_175.pdf, Table on p. 2, text pp. 3-4,
flow chart p. 7 (Appendix I). Checked 2026-10-24 (``docs/verification.md`` D42).

The standard, in the order of the p. 7 flow chart:

1. denominator n < 30 or effective n < 30 -> **unreliable** (NCHS: suppress). Effective n
   is p(1-p)/var(p), capped at n; when p is 0 or 1 it is n.
2. Korn-Graubard 95% interval width >= 0.30 -> **unreliable**.
3. width <= 0.05 -> present, unless the number of events is 0 (or n) or df < 8 -> **review**.
4. 0.05 < width < 0.30: relative width (width / p) > 130% -> **unreliable**; otherwise
   present unless the number of events is 0 (or n) or df < 8 -> **review**.
5. 0 events: the relative width is undefined (p = 0), so it is not checked. As NCHS p. 3
   says, an estimate "based on 0 events ... that meet[s] absolute CI and degrees of
   freedom criteria should be flagged" -> **review** (flow chart p. 7: "Is number of
   events = 0? YES -> Statistical review").

On top of NCHS, the project adds one stricter rule (:func:`low_events`): an estimate that
NCHS would call reliable but that rests on fewer than 10 unweighted events is downgraded to
**review** ("low_events<10"). NCHS sets no minimum numerator; this is our own caution.

"review" is NCHS's "flag for statistical review by the clearance official". This module
only labels estimates; it suppresses nothing. Disclosure suppression (fewer than 30
unweighted respondents) is a separate rule in :mod:`curbcut_ingest.disclosure`.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

MIN_N = 30
"""Minimum denominator and effective denominator sample size (NCHS p. 2)."""
MAX_ABS_WIDTH = 0.30
"""Absolute CI width at or above which a proportion is suppressed (p. 2)."""
SMALL_ABS_WIDTH = 0.05
"""Absolute CI width at or below which the relative width is not checked (p. 2)."""
MAX_REL_WIDTH = 1.30
"""Relative CI width (width / p) above which a proportion is suppressed (p. 2: 130%)."""
MIN_DF = 8
"""Degrees of freedom below which a proportion goes to statistical review (p. 2)."""
MIN_EVENTS = 10
"""Project rule, not NCHS: fewer unweighted events than this downgrades reliable to review."""

RELIABLE, REVIEW, UNRELIABLE = "reliable", "review", "unreliable"
FLAGS = (RELIABLE, REVIEW, UNRELIABLE)


@dataclass(frozen=True)
class Flag:
    flag: str
    reason: str


def effective_n(estimate: float, se: float, n: int) -> float:
    """NCHS effective sample size p(1-p)/var(p), capped at n; n when p is 0 or 1 or se is 0."""
    if estimate <= 0 or estimate >= 1 or se <= 0:
        return float(n)
    return min(float(n), estimate * (1 - estimate) / se**2)


def nchs_flag(
    *,
    estimate: float,
    ci_low: float,
    ci_high: float,
    n: int,
    n_effective: float,
    events: int,
    df: float | None,
) -> Flag:
    """Classify one proportion under the NCHS standard. ``df`` None means not applicable."""
    if n < MIN_N or n_effective < MIN_N:
        return Flag(UNRELIABLE, "n_effective<30" if n >= MIN_N else "n<30")
    if any(math.isnan(v) for v in (estimate, ci_low, ci_high)):
        return Flag(UNRELIABLE, "no_interval")
    width = ci_high - ci_low
    if width >= MAX_ABS_WIDTH:
        return Flag(UNRELIABLE, "ci_width>=0.30")
    reasons = []
    zero = events == 0 or estimate <= 0
    if width > SMALL_ABS_WIDTH and not zero and width / estimate > MAX_REL_WIDTH:
        return Flag(UNRELIABLE, "relative_ci_width>130%")
    if zero or events == n:
        reasons.append("zero_events" if zero else "all_events")
    if df is not None and df < MIN_DF:
        reasons.append("df<8")
    if reasons:
        return Flag(REVIEW, ";".join(reasons))
    return Flag(RELIABLE, "")


def low_events(flag: Flag, events: int) -> Flag:
    """Downgrade a reliable estimate resting on 1-9 unweighted events to review."""
    if flag.flag == RELIABLE and 0 < events < MIN_EVENTS:
        return Flag(REVIEW, f"low_events<{MIN_EVENTS}")
    return flag
