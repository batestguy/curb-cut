"""Check that our DHS 2024 processing reproduces the published NDHS 2024 report (P4a step 0).

Recomputes Table 14.1 (household population 5+) and Tables 14.2.1/14.2.2 (women and men
15+, by state) of the final report (FR395) from the PR recode, using the report's own
conventions, and compares them with the transcribed figures in
``data/public/ndhs_report/``:

- de facto household members (``hv103 == 1``), weight ``hv005 / 1e6``;
- every member in the age range is in the denominator, including "don't know" and missing
  answers (the report's note: "Total includes 56 persons with unknown or missing
  information");
- members whose age is "don't know" (``hv105 == 98``; 49 people, weighted 55.6) were asked
  the module and count as 15+ in the totals, though in no age band. Without them the
  weighted totals fall 56 short of the report's.
- the highest level in at least one domain is DHS's own ``hdis9``;
- ``number`` is the weighted count.

Only point estimates are compared (the report publishes no standard errors). Our recomputed
cells stay in ``data/restricted/derived/``; the console shows only the comparison, and every
compared cell holds hundreds of respondents (a cell under the disclosure threshold is never
printed).

Run (local only): ``uv run python -I -m curbcut_ingest.validate_ndhs``.
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

import numpy as np
import pandas as pd

from curbcut_ingest.restricted import common as c
from curbcut_ingest.restricted.dhs2024 import DEFAULT_INPUT, DOMAIN_VARS
from curbcut_ingest.states import StateLookup

BENCHMARK = c.ROOT / "data" / "public" / "ndhs_report"
OUT = c.DERIVED / "validation"
COLUMNS = ["hv005", "hv103", "hv104", "hv105", "shstate", *DOMAIN_VARS.values(), "hdis9"]
AGE_UNKNOWN = 98
AGE_ROWS = {
    "age_5_9": (5, 9),
    "age_10_14": (10, 14),
    "age_15_19": (15, 19),
    "age_20_29": (20, 29),
    "age_30_39": (30, 39),
    "age_40_49": (40, 49),
    "age_50_59": (50, 59),
    "age_60_plus": (60, 97),
    "age_15_plus": (15, AGE_UNKNOWN),
    "total": (5, AGE_UNKNOWN),
}
SEX = {1: "male", 2: "female"}
TOLERANCE = 0.05
"""Published figures are rounded to one decimal, so an exact reproduction is within 0.05."""


def prepare(raw: pd.DataFrame) -> pd.DataFrame:
    """De facto members aged 5+, with the codes the report tabulates (pure; tested)."""
    age = c.to_num(raw["hv105"])
    keep = (c.to_num(raw["hv103"]) == 1) & (((age >= 5) & (age <= 97)) | (age == AGE_UNKNOWN))
    out = pd.DataFrame(index=raw.index)
    out["weight"] = c.to_num(raw["hv005"]) / 1e6
    out["age"] = age
    out["sex"] = c.to_num(raw["hv104"]).map(SEX)
    out["state_code"] = c.to_num(raw["shstate"])
    for domain, var in DOMAIN_VARS.items():
        out[domain] = c.to_num(raw[var])
    out["highest"] = c.to_num(raw["hdis9"])
    return out[keep].reset_index(drop=True)


def _pct(mask: pd.Series, weight: pd.Series) -> float:
    total = weight.sum()
    return float(100 * weight[mask.fillna(False).astype(bool)].sum() / total) if total else np.nan


def table_14_1(people: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for domain in DOMAIN_VARS:
        level, w = people[domain], people["weight"]
        rows.append(
            {
                "row": domain,
                "no_difficulty": _pct(level == 1, w),
                "some": _pct(level == 2, w),
                "a_lot": _pct(level == 3, w),
                "cannot": _pct(level == 4, w),
                "dont_know": _pct(level == 8, w),
                "a_lot_or_cannot": _pct(level.isin([3, 4]), w),
                "number": w.sum(),
                "n_unweighted": len(people),
            }
        )
    for name, (lo, hi) in AGE_ROWS.items():
        sub = people[(people["age"] >= lo) & (people["age"] <= hi)]
        level, w = sub["highest"], sub["weight"]
        rows.append(
            {
                "row": name,
                "no_difficulty": _pct(level == 1, w),
                "some": _pct(level == 2, w),
                "a_lot": _pct(level == 3, w),
                "cannot": _pct(level == 4, w),
                "dont_know": _pct(level == 8, w),
                "a_lot_or_cannot": _pct(level.isin([3, 4]), w),
                "number": w.sum(),
                "n_unweighted": len(sub),
            }
        )
    return pd.DataFrame(rows)


def _row_14_2(sub: pd.DataFrame) -> dict[str, float]:
    w = sub["weight"]
    level = sub["highest"]
    severe = sub[list(DOMAIN_VARS)].isin([3, 4]).sum(axis=1)
    row = {"no_difficulty": _pct(level == 1, w)}
    for domain in DOMAIN_VARS:
        row[domain] = _pct(sub[domain].isin([2, 3, 4]), w)
    row |= {
        "some": _pct(level == 2, w),
        "a_lot": _pct(level == 3, w),
        "cannot": _pct(level == 4, w),
        "a_lot_or_cannot": _pct(level.isin([3, 4]), w),
        "multi_domain": _pct(severe >= 2, w),
        "number": w.sum(),
        "n_unweighted": float(len(sub)),
    }
    return row


def table_14_2(people: pd.DataFrame, state_names: dict[int, str]) -> pd.DataFrame:
    adults = people[people["age"] >= 15].assign(state=lambda f: f["state_code"].map(state_names))
    rows = []
    for (sex, state), sub in adults.groupby(["sex", "state"]):
        rows.append({"sex": sex, "state": state} | _row_14_2(sub))
    for sex, sub in adults.groupby("sex"):
        rows.append({"sex": sex, "state": "Total"} | _row_14_2(sub))
    return pd.DataFrame(rows)


def compare(ours: pd.DataFrame, published: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    """Long table of published vs recomputed cells, with the absolute difference."""
    value_cols = [col for col in published.columns if col not in keys]
    merged = published.merge(ours, on=keys, how="left", suffixes=("_pub", "_ours"))
    if merged[[f"{value_cols[0]}_ours"]].isna().any().any():
        raise ValueError("some published rows have no recomputed counterpart")
    long = []
    for col in value_cols:
        part = merged[[*keys, f"{col}_pub", f"{col}_ours", "n_unweighted"]].copy()
        part.columns = [*keys, "published", "ours", "n_unweighted"]
        part.insert(len(keys), "column", col)
        long.append(part)
    out = pd.concat(long, ignore_index=True)
    is_count = out["column"] == "number"
    out["diff"] = (out["ours"] - out["published"]).abs()
    # Weighted counts are published as whole numbers.
    out["ok"] = np.where(is_count, out["diff"] < 0.5 + 1e-9, out["diff"] <= TOLERANCE + 1e-9)
    return out


def _report(name: str, result: pd.DataFrame, keys: list[str]) -> int:
    if (result["n_unweighted"] < c.DISCLOSURE_THRESHOLD).any():
        raise ValueError(f"{name}: a compared cell is under the disclosure threshold")
    bad = result[~result["ok"]]
    pct = result[result["column"] != "number"]
    c.log(
        f"{name}: {len(result)} cells, {int(result['ok'].sum())} reproduce the published figure "
        f"(within {TOLERANCE} points; counts within 0.5); largest percentage gap "
        f"{pct['diff'].max():.3f} points"
    )
    for _, row in bad.head(40).iterrows():
        where = " / ".join(str(row[k]) for k in keys)
        c.log(
            f"  differs: {where} / {row['column']}: "
            f"published {row['published']}, ours {row['ours']:.3f}"
        )
    if len(bad) > 40:
        c.log(f"  ... and {len(bad) - 40} more")
    return len(bad)


@c.safe_main
def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Reproduce NDHS 2024 Tables 14.1 and 14.2.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--benchmark", type=Path, default=BENCHMARK)
    parser.add_argument("--out-dir", type=Path, default=OUT)
    args = parser.parse_args(argv)

    raw, meta = c.read_dta(args.input, COLUMNS)
    lookup = StateLookup.from_seeds()
    states = {
        code: s.state for code, s in lookup.map_codes(c.value_labels(meta, "shstate")).items()
    }
    people = prepare(raw)
    c.log(f"de facto members aged 5+: {c.masked(len(people))} unweighted")

    published_1 = pd.read_csv(args.benchmark / "fr395_table14_1.csv")
    published_2 = pd.read_csv(args.benchmark / "fr395_table14_2.csv")
    published_2["state"] = [
        name if name == "Total" else lookup.resolve(name).state for name in published_2["state"]
    ]

    result_1 = compare(table_14_1(people), published_1, ["row"])
    result_2 = compare(table_14_2(people, states), published_2, ["sex", "state"])
    args.out_dir.mkdir(parents=True, exist_ok=True)
    result_1.to_csv(args.out_dir / "ndhs_table14_1.csv", index=False)
    result_2.to_csv(args.out_dir / "ndhs_table14_2.csv", index=False)

    failures = _report("Table 14.1", result_1, ["row"])
    failures += _report("Tables 14.2.1/14.2.2", result_2, ["sex", "state"])
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
