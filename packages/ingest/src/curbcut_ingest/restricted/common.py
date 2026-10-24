"""Shared schema and safe I/O for the restricted-zone harmonisers.

**Data-handling rule.** Microdata must never reach a log, a traceback or an LLM. So:

* :func:`read_dta` reads only the named columns, with codes rather than value labels;
* :func:`masked` is the only way a count is printed, and shows any count under 30 as "<30";
* :func:`safe_main` catches every exception and prints its type and location only, never
  its message, because pandas and pyreadstat messages can quote a value.

Common person-level schema (one row per person aged 5+ who answered the module):

``source, person_id, state, state_code, zone, sector, sex, age, age_group, age_band,
weight, stratum, psu`` plus disability columns. The six Washington Group domains are coded
1-4 (1 no difficulty ... 4 cannot do at all) with "don't know", refusals and out-of-route
answers set to missing. ``disability3`` is the WG-SS DISABILITY3 indicator (WG Doc 7A).
"""

from __future__ import annotations

import functools
import sys
import traceback
from collections.abc import Callable, Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any, cast

import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
RESTRICTED = ROOT / "data" / "restricted"
DERIVED = RESTRICTED / "derived"

DISCLOSURE_THRESHOLD = 30
"""Cells with fewer unweighted respondents than this are suppressed (and masked in logs)."""

WG_DOMAINS = ("seeing", "hearing", "walking", "cognition", "selfcare", "communication")
WG_LEVELS = (1, 2, 3, 4)

COMMON_COLUMNS = (
    "source",
    "person_id",
    "state",
    "state_code",
    "zone",
    "sector",
    "sex",
    "age",
    "age_group",
    "age_band",
    "weight",
    "stratum",
    "psu",
)

AGE_BANDS = ((5, 9, "5-9"), (10, 17, "10-17"), (18, 29, "18-29"), (30, 49, "30-49"))
AGE_BANDS_OPEN = ((50, 64, "50-64"), (65, 200, "65+"))


def to_num(values: pd.Series) -> pd.Series:
    """Numeric codes as a float Series (anything non-numeric becomes NaN)."""
    return pd.Series(pd.to_numeric(values, errors="coerce"), index=values.index, dtype="float64")


def masked(count: int | float, threshold: int = DISCLOSURE_THRESHOLD) -> str:
    """A count as safe text: any count from 1 to threshold-1 becomes "<threshold"."""
    count = int(count)
    return f"<{threshold}" if 0 < count < threshold else f"{count:,}"


def log(message: str) -> None:
    print(message, flush=True)


def safe_main(func: Callable[..., int]) -> Callable[..., int]:
    """Run a CLI entry point so that no exception message (which may quote data) is printed."""

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> int:
        try:
            return func(*args, **kwargs)
        except SystemExit:
            raise
        except BaseException as exc:
            frames = traceback.extract_tb(exc.__traceback__)
            ours = [f for f in frames if "curbcut_ingest" in f.filename][-3:]
            where = ", ".join(f"{Path(f.filename).name}:{f.lineno}" for f in [*ours, frames[-1]])
            print(f"failed: {type(exc).__name__} at {where} (message withheld)", file=sys.stderr)
            return 1

    return wrapper


def read_dta(path: Path, columns: Sequence[str]) -> tuple[pd.DataFrame, Any]:
    """Read only ``columns`` from a Stata file, as codes. Returns (frame, metadata)."""
    import pyreadstat

    _, meta = pyreadstat.read_dta(str(path), metadataonly=True)
    missing = [c for c in columns if c not in meta.column_names]
    if missing:
        # Column names are metadata, safe to print.
        raise KeyError(f"{path.name}: columns not found: {missing}")
    frame, _ = pyreadstat.read_dta(
        str(path), usecols=list(columns), apply_value_formats=False, output_format="pandas"
    )
    return cast(pd.DataFrame, frame), meta


def value_labels(meta: Any, column: str) -> dict[int, str]:
    """The value-label set (metadata) attached to ``column``."""
    return {int(k): str(v) for k, v in meta.value_labels[meta.variable_to_label[column]].items()}


def wg_scale(values: pd.Series, valid: Iterable[int] = WG_LEVELS) -> pd.Series:
    """Keep codes 1-4; anything else (don't know, refused, too young, blank) -> missing."""
    numeric = to_num(values)
    return numeric.where(numeric.isin(list(valid))).astype("Int8")


def worse_of(*items: pd.Series) -> pd.Series:
    """Combine items on the 1-4 scale into the worse (higher) level.

    A person is at level 3+ if any item is 3+, even when another is missing. Otherwise the
    combined level is known only when every item is answered; else it is missing (the
    missing item could have been worse).
    """
    frame = pd.concat(list(items), axis=1)
    worst = frame.max(axis=1, skipna=True)
    complete = frame.notna().all(axis=1)
    known = complete | (worst >= 3)
    return worst.where(known).astype("Int8")


def disability3(domains: pd.DataFrame) -> pd.Series:
    """WG-SS DISABILITY3: 1 if any domain is 3 or 4; 0 if all six are answered and none is;
    missing otherwise (WG Doc 7A)."""
    any_severe = (domains >= 3).any(axis=1)
    all_answered = domains.notna().all(axis=1)
    out = pd.Series(pd.NA, index=domains.index, dtype="Int8")
    out[all_answered] = 0
    out[any_severe.fillna(False).astype(bool)] = 1
    return out


def age_group(age: pd.Series) -> pd.Series:
    """'5-17' or '18+'; missing for ages under 5 or unknown."""
    age = to_num(age)
    out = pd.Series(pd.NA, index=age.index, dtype="string")
    out[(age >= 5) & (age <= 17)] = "5-17"
    out[age >= 18] = "18+"
    return out


def age_band(age: pd.Series) -> pd.Series:
    age = to_num(age)
    out = pd.Series(pd.NA, index=age.index, dtype="string")
    for lo, hi, label in AGE_BANDS + AGE_BANDS_OPEN:
        out[(age >= lo) & (age <= hi)] = label
    return out


def recode(values: pd.Series, mapping: Mapping[int, str]) -> pd.Series:
    """Map codes to labels; unmapped codes become missing."""
    numeric = to_num(values)
    return numeric.map(lambda v: mapping.get(int(v)) if pd.notna(v) else pd.NA).astype("string")


def attach_state(out: pd.DataFrame, codes: pd.Series, states: Mapping[int, Any]) -> None:
    """Set state, state_code and zone on ``out`` from source state codes."""
    numeric = to_num(codes)
    found = numeric.map(lambda v: states.get(int(v)), na_action="ignore")
    for column in ("state", "state_code", "zone"):
        out[column] = found.map(lambda s, col=column: getattr(s, col), na_action="ignore").astype(
            "string"
        )


def code_text(values: pd.Series) -> pd.Series:
    """Identifier codes as text: whole numbers without a decimal point, text stripped."""
    numeric = to_num(values)
    whole = numeric.notna() & (numeric == numeric.round())
    if bool((whole | values.isna()).all()):
        return numeric.astype("Int64").astype("string")
    return values.astype("string").str.strip()


def join_codes(prefix: str, *parts: pd.Series) -> pd.Series:
    """``prefix-part1-part2...`` with each part as :func:`code_text`."""
    out = pd.Series(prefix, index=parts[0].index, dtype="string")
    for part in parts:
        out = out + "-" + code_text(part)
    return out


SEX = {1: "male", 2: "female"}
SECTOR = {1: "urban", 2: "rural"}


def report_counts(title: str, series: pd.Series) -> None:
    """Log the frequency of each code in ``series`` (codes are metadata), masked."""
    counts = series.value_counts(dropna=False).sort_index()
    parts = [f"{'missing' if pd.isna(cast(Any, k)) else k}: {masked(v)}" for k, v in counts.items()]
    log(f"  {title}: " + ", ".join(parts))


def report_match(title: str, matched: int, total: int) -> None:
    log(f"  {title}: {masked(matched)} of {masked(total)} matched")


def write_parquet(frame: pd.DataFrame, name: str, out_dir: Path = DERIVED) -> Path:
    """Write a harmonised frame to the git-ignored derived folder."""
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{name}.parquet"
    frame.to_parquet(path, index=False, compression="zstd")
    shown = path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else path.name
    log(f"wrote {masked(len(frame))} person rows to {shown}")
    return path


def finish(frame: pd.DataFrame, extra: Sequence[str]) -> pd.DataFrame:
    """Order columns as the common schema, then the source's own columns."""
    return frame.loc[:, [*COMMON_COLUMNS, *extra]].reset_index(drop=True)
