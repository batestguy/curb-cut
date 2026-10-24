"""NCHS proportion standard, including rows from the report's own worked examples."""

from __future__ import annotations

import math

import pytest
from curbcut_ingest.precision import (
    RELIABLE,
    REVIEW,
    UNRELIABLE,
    Flag,
    effective_n,
    low_events,
    nchs_flag,
)


def flag(
    p: float,
    lo: float,
    hi: float,
    *,
    n: int = 500,
    n_eff: float | None = None,
    events: int | None = None,
    df: float | None = 30,
):
    return nchs_flag(
        estimate=p,
        ci_low=lo,
        ci_high=hi,
        n=n,
        n_effective=n if n_eff is None else n_eff,
        events=max(1, round(p * n)) if events is None else events,
        df=df,
    )


def test_sample_size_rules() -> None:
    assert flag(0.5, 0.4, 0.6, n=29).reason == "n<30"
    assert flag(0.5, 0.4, 0.6, n=100, n_eff=29.9).reason == "n_effective<30"


# Parker et al. 2017, Appendix II (proportions, not percent).
@pytest.mark.parametrize(
    ("p", "lo", "hi", "n", "n_eff", "df", "expected"),
    [
        (0.005, 0.001, 0.016, 460, 460, 15, "reliable"),  # Table I, NH white elevated
        (0.020, 0.003, 0.064, 447, 145.3, 13, UNRELIABLE),  # Table I, NH black (305%)
        (0.522, 0.420, 0.623, 169, 124.0, 11, "reliable"),  # Table II, Hispanic men
        (0.478, 0.360, 0.597, 74, 74, 7, REVIEW),  # Table II, NH Asian men: df 7
    ],
)
def test_report_examples(p, lo, hi, n, n_eff, df, expected) -> None:
    assert flag(p, lo, hi, n=n, n_eff=n_eff, df=df).flag == expected


def test_width_rules() -> None:
    assert flag(0.5, 0.3, 0.6).reason == "ci_width>=0.30"
    assert flag(0.05, 0.01, 0.12).reason == "relative_ci_width>130%"
    assert flag(0.3, 0.2, 0.4).flag == "reliable"  # width 0.2, relative 67%
    assert flag(0.01, 0.005, 0.02).flag == "reliable"  # width <= 0.05: relative not checked


def test_review_rules() -> None:
    assert flag(0.0, 0.0, 0.007, events=0).reason == "zero_events"
    assert flag(1.0, 0.993, 1.0, n=500, events=500).reason == "all_events"
    assert flag(0.3, 0.25, 0.35, df=5).reason == "df<8"
    assert flag(0.3, 0.25, 0.35, df=None).flag == "reliable"
    assert flag(math.nan, math.nan, math.nan, events=1).reason == "no_interval"


def test_effective_n() -> None:
    assert effective_n(0.0, 0.0, 100) == 100
    assert effective_n(0.5, 0.05, 1000) == pytest.approx(100)
    assert effective_n(0.5, 0.001, 1000) == 1000  # capped at n


def test_zero_events_go_to_review_not_relative_width() -> None:
    # p = 0: the relative width is undefined, so NCHS sends it to review (p. 3, flow chart).
    zero_wide = flag(0.0, 0.0, 0.08, n=60, events=0)
    assert zero_wide.flag == REVIEW
    assert zero_wide.reason == "zero_events"
    assert flag(0.0, 0.0, 0.35, n=60, events=0).flag == UNRELIABLE  # width rule still applies


def test_low_events_rule() -> None:
    assert low_events(Flag(RELIABLE, ""), 9) == Flag(REVIEW, "low_events<10")
    assert low_events(Flag(RELIABLE, ""), 1).flag == REVIEW
    assert low_events(Flag(RELIABLE, ""), 10).flag == RELIABLE
    assert low_events(Flag(REVIEW, "zero_events"), 0) == Flag(REVIEW, "zero_events")
    assert low_events(Flag(UNRELIABLE, "n<30"), 3).flag == UNRELIABLE
