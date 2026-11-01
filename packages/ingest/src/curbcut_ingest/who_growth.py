"""WHO Child Growth Standards (2006): length/height-for-age and weight-for-age z-scores.

Implemented directly from WHO's published LMS tables, as WHO Anthro computes them:

* ``z = ((y / M) ** L - 1) / (S * L)`` (``log(y / M) / S`` when ``L == 0``), with M, L, S
  looked up by sex and age in whole days (0-1856);
* weight-for-age is "restricted": beyond +/-3 SD the z-score is extended linearly using
  the distance between the 2 and 3 SD cut-offs (WHO Anthro technical report, ch. 7);
  length/height-for-age has ``L = 1`` throughout, so it needs no restriction;
* length is measured lying under 731 days and height standing from 731 days; a child
  measured the other way is corrected by 0.7 cm (standing under 731 days: +0.7; lying
  from 731 days: -0.7). With the position unknown nothing is corrected;
* age known only in completed months is converted to days as ``months * 30.4375``
  (WHO Anthro's convention), rounded to the nearest day;
* implausible values are flagged and set missing: height-for-age outside [-6, 6],
  weight-for-age outside [-6, 5] (WHO flags).

The tables are not in git (their licence for redistribution was not checked). Download the
four "expanded tables" z-score workbooks by hand into ``data/sources/who-growth/`` from
``https://cdn.who.int/media/docs/default-source/child-growth/child-growth-standards/
indicators/`` + ``length-height-for-age/expandable-tables/lhfa-{boys,girls}-zscore-
expanded-tables.xlsx`` and ``weight-for-age/expanded-tables/wfa-{boys,girls}-zscore-
expanded-tables.xlsx``. Each file is checked against :data:`SHA256` on load.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
WHO_DIR = ROOT / "data" / "sources" / "who-growth"

FILES = {
    ("lhfa", "male"): "lhfa-boys-zscore-expanded-tables.xlsx",
    ("lhfa", "female"): "lhfa-girls-zscore-expanded-tables.xlsx",
    ("wfa", "male"): "wfa-boys-zscore-expanded-tables.xlsx",
    ("wfa", "female"): "wfa-girls-zscore-expanded-tables.xlsx",
}
SHA256 = {
    "lhfa-boys-zscore-expanded-tables.xlsx": (
        "c4b1c9029ab9751a5f0888e32f35c7c0287a16d361885cf911ecf23b3f7f6b4f"
    ),
    "lhfa-girls-zscore-expanded-tables.xlsx": (
        "6aa2876319449a6b1f4d825848128902114ff53c67b92b86a0c5140846013059"
    ),
    "wfa-boys-zscore-expanded-tables.xlsx": (
        "b5b4748c6bfa5230e2eddafa1767629c349178b08d457f400b59422b8bfef86c"
    ),
    "wfa-girls-zscore-expanded-tables.xlsx": (
        "ee3ae12cb96c6c5541cdf43665c03ce6c984f877859a183a5f6104eb06a49a6e"
    ),
}
"""SHA-256 of the files as downloaded from cdn.who.int on 2026-10-30."""

MAX_DAY = 1856
DAYS_PER_MONTH = 30.4375
LYING_UNTIL_DAY = 731
POSITION_CORRECTION_CM = 0.7
FLAGS = {"lhfa": (-6.0, 6.0), "wfa": (-6.0, 5.0)}

Tables = Mapping[tuple[str, str], pd.DataFrame]
"""(indicator, sex) -> frame indexed by day with columns L, M, S."""


class GrowthTableError(ValueError):
    """A WHO table is missing, altered or malformed."""


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_tables(directory: Path = WHO_DIR) -> dict[tuple[str, str], pd.DataFrame]:
    """Read and hash-check the four WHO workbooks."""
    tables: dict[tuple[str, str], pd.DataFrame] = {}
    for key, name in FILES.items():
        path = directory / name
        if not path.is_file():
            raise GrowthTableError(f"missing {name}: see curbcut_ingest.who_growth docstring")
        if sha256(path) != SHA256[name]:
            raise GrowthTableError(f"{name}: SHA-256 differs from the pinned value")
        frame = pd.read_excel(path, usecols=["Day", "L", "M", "S"])
        tables[key] = check_table(frame, name)
    return tables


def check_table(frame: pd.DataFrame, name: str = "table") -> pd.DataFrame:
    """Index by day; require days 0..1856 exactly once."""
    out = frame.astype({"Day": "int64"}).set_index("Day")[["L", "M", "S"]].astype("float64")
    if out.index.tolist() != list(range(MAX_DAY + 1)):
        raise GrowthTableError(f"{name}: days are not 0..{MAX_DAY}")
    return out


def age_days_from_months(months: pd.Series) -> pd.Series:
    """Completed months -> whole days (WHO Anthro: months x 30.4375)."""
    days = pd.to_numeric(months, errors="coerce").astype("float64") * DAYS_PER_MONTH
    return days.round()


def lms_z(y: np.ndarray, lam: np.ndarray, mu: np.ndarray, sigma: np.ndarray) -> np.ndarray:
    """The plain LMS z-score."""
    with np.errstate(divide="ignore", invalid="ignore"):
        boxcox = ((y / mu) ** lam - 1) / (sigma * lam)
        return np.where(lam == 0, np.log(y / mu) / sigma, boxcox)


def lms_value(z: float, lam: np.ndarray, mu: np.ndarray, sigma: np.ndarray) -> np.ndarray:
    """The measurement at a given z (the inverse of :func:`lms_z`)."""
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(lam == 0, mu * np.exp(sigma * z), mu * (1 + lam * sigma * z) ** (1 / lam))


def restricted_z(y: np.ndarray, lam: np.ndarray, mu: np.ndarray, sigma: np.ndarray) -> np.ndarray:
    """WHO's restricted z for weight-based indicators: linear beyond +/-3 SD."""
    z = lms_z(y, lam, mu, sigma)
    sd3p, sd2p = lms_value(3, lam, mu, sigma), lms_value(2, lam, mu, sigma)
    sd3n, sd2n = lms_value(-3, lam, mu, sigma), lms_value(-2, lam, mu, sigma)
    above = 3 + (y - sd3p) / (sd3p - sd2p)
    below = -3 + (y - sd3n) / (sd2n - sd3n)
    return np.where(z > 3, above, np.where(z < -3, below, z))


def _lookup(table: pd.DataFrame, days: pd.Series) -> tuple[np.ndarray, ...]:
    valid = days.notna() & (days >= 0) & (days <= MAX_DAY)
    idx = days.where(valid, 0).astype("int64").to_numpy()
    params = table.to_numpy()[idx]
    nan = np.where(valid.to_numpy(), 1.0, np.nan)
    return params[:, 0] * nan, params[:, 1] * nan, params[:, 2] * nan


def zscores(
    tables: Tables,
    indicator: str,
    sex: pd.Series,
    age_days: pd.Series,
    value: pd.Series,
) -> pd.Series:
    """z-scores for one indicator; sex is "male"/"female"; out of range or flagged -> NaN."""
    out = pd.Series(np.nan, index=value.index, dtype="float64")
    y = pd.to_numeric(value, errors="coerce").astype("float64")
    for s in ("male", "female"):
        rows = (sex == s).fillna(False).to_numpy(dtype=bool)
        if not rows.any():
            continue
        lam, mu, sigma = _lookup(tables[(indicator, s)], age_days[rows])
        ys = y[rows].to_numpy()
        z = restricted_z(ys, lam, mu, sigma) if indicator == "wfa" else lms_z(ys, lam, mu, sigma)
        out[rows] = z
    lo, hi = FLAGS[indicator]
    out[(y <= 0) | (out < lo) | (out > hi)] = np.nan
    return out


def standardised_height(height: pd.Series, lying: pd.Series, age_days: pd.Series) -> pd.Series:
    """Correct length/height by 0.7 cm when measured in the other position (WHO rule).

    ``lying`` is True (measured lying), False (standing) or missing (unknown: unchanged).
    """
    h = pd.to_numeric(height, errors="coerce").astype("float64")
    lie = lying.astype("boolean")
    standing_young = (lie == False) & (age_days < LYING_UNTIL_DAY)  # noqa: E712
    lying_old = (lie == True) & (age_days >= LYING_UNTIL_DAY)  # noqa: E712
    h = h.where(~standing_young.fillna(False), h + POSITION_CORRECTION_CM)
    return h.where(~lying_old.fillna(False), h - POSITION_CORRECTION_CM)
