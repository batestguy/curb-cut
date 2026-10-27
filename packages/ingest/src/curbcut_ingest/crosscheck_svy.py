"""Cross-check the published DHS 2024 state estimates (R ``survey``) with Python ``svy``.

P4a step 0 (``PLAN.md``): the state estimates in ``data/public/aggregates/dhs2024_state.csv``
come from ``R/estimate.R``. This recomputes them independently with ``svy`` from the
harmonised person-level file, using the same design (PSU ``psu``, strata ``stratum``,
weight ``weight``, Taylor linearisation; a stratum with one PSU is centred on the grand mean,
as R's ``survey.lonely.psu = "adjust"`` does), and compares every published (unsuppressed)
cell. The console shows only the size of the differences.

Run (local only): ``uv run python -I -m curbcut_ingest.crosscheck_svy``.
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

import pandas as pd
import polars as pl
import svy

from curbcut_ingest.aggregate import wg_indicators
from curbcut_ingest.restricted import common as c

PUBLIC = c.ROOT / "data" / "public" / "aggregates" / "dhs2024_state.csv"
PERSONS = c.DERIVED / "dhs2024.parquet"
ESTIMATE_TOL = 1e-6
SE_TOL = 0.05
"""Relative SE difference allowed: lonely-PSU and domain-singleton rules differ slightly."""


def svy_estimates(frame: pd.DataFrame, measures: list[str]) -> pd.DataFrame:
    indicators = pd.DataFrame(wg_indicators(frame))[measures].astype("float64")
    data = pd.concat(
        [frame[["psu", "stratum", "weight", "state_code", "age_group"]], indicators], axis=1
    )
    data = data[data["age_group"].notna()]
    design = svy.Design(
        stratum="stratum",
        psu="psu",
        wgt="weight",
        singleton=svy.Singleton(svy.SingletonMethod.CENTER),
    )
    sample = svy.Sample(pl.from_pandas(data), design)
    rows = []
    for age in ("18+", "5-17"):
        for measure in measures:
            est = sample.estimation.mean(
                measure, by="state_code", where=pl.col("age_group") == age, drop_nulls=True
            )
            assert isinstance(est, svy.Estimate)  # one measure in, one Estimate out
            out = est.to_polars().to_pandas()
            out["measure"], out["age_group"] = measure, age
            rows.append(out)
    return pd.concat(rows, ignore_index=True)


@c.safe_main
def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Cross-check DHS state estimates with svy.")
    parser.add_argument("--persons", type=Path, default=PERSONS)
    parser.add_argument("--public", type=Path, default=PUBLIC)
    args = parser.parse_args(argv)

    public = pd.DataFrame(pd.read_csv(args.public))
    public = pd.DataFrame(public[(~public["suppressed"]) & (public["sex"] == "all")])
    measures = sorted(str(m) for m in public["measure"].unique() if "_level_" not in str(m))
    public = pd.DataFrame(public[public["measure"].isin(measures)])

    ours = svy_estimates(pd.read_parquet(args.persons), measures)
    ours = ours.rename(columns={"est": "svy_estimate", "se": "svy_se", "state_code": "geography"})
    merged = public.merge(
        ours[["measure", "age_group", "geography", "svy_estimate", "svy_se"]],
        on=["measure", "age_group", "geography"],
        how="left",
    )
    missing = int(merged["svy_estimate"].isna().to_numpy().sum())
    est_gap = (merged["estimate"] - merged["svy_estimate"]).abs()
    has_se = merged["se"] > 0
    se_gap = ((merged["se"] - merged["svy_se"]).abs() / merged["se"]).where(has_se)
    c.log(
        f"{len(merged)} published state cells compared ({missing} without an svy counterpart)\n"
        f"  estimate: largest absolute difference {est_gap.max():.2e}; "
        f"{int((est_gap > ESTIMATE_TOL).to_numpy().sum())} above {ESTIMATE_TOL:.0e}\n"
        f"  SE: median relative difference {se_gap.median():.2%}, largest {se_gap.max():.2%}; "
        f"{int((se_gap > SE_TOL).to_numpy().sum())} above {SE_TOL:.0%}"
    )
    worst = merged.assign(se_gap=se_gap).nlargest(5, "se_gap")
    for _, row in worst.iterrows():
        c.log(
            f"  largest SE gaps: {row['measure']} / {row['age_group']} / {row['geography']}: "
            f"R {row['se']:.5f}, svy {row['svy_se']:.5f}"
        )
    ok = missing == 0 and (est_gap <= ESTIMATE_TOL).all() and (se_gap.fillna(0) <= SE_TOL).all()
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
