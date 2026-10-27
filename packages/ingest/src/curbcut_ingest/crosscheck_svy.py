"""Cross-check every published DHS 2024 cell (R ``survey``) with Python ``svy``.

P4a steps 0-1 (``PLAN.md``): the DHS cells in ``data/public/aggregates/dhs2024_*.csv``
(state, national and zone files; every sex, every breakdown) come from ``R/estimate.R``.
This recomputes them independently with ``svy`` from the harmonised person-level file,
using the same design (PSU ``psu``, strata ``stratum``, weight ``weight``, Taylor
linearisation; a stratum with one PSU is centred on the grand mean, as R's
``survey.lonely.psu = "adjust"`` does), and compares every published (unsuppressed) cell.
The console shows only the size of the differences.

Each published row is matched through a cell key: its geography, then its sex when it is
not "all", then its breakdown level when the breakdown is not "all". svy estimates the
mean by that key within the row's age group, one call per cell type, age group and measure.

Run (local only): ``uv run python -I -m curbcut_ingest.crosscheck_svy``.
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

import pandas as pd
import polars as pl
import svy

from curbcut_ingest.aggregate import BREAKDOWN_COLUMNS, GEOGRAPHIES, wg_indicators
from curbcut_ingest.restricted import common as c

AGGREGATES = c.ROOT / "data" / "public" / "aggregates"
PUBLIC = tuple(AGGREGATES / f"dhs2024_{level}.csv" for level in ("state", "national", "zone"))
PERSONS = c.DERIVED / "dhs2024.parquet"
ESTIMATE_TOL = 1e-6
SE_TOL = 0.05
"""Relative SE difference allowed: lonely-PSU and domain-singleton rules differ slightly."""


def cell_type(row: pd.Series) -> tuple[str, bool, str]:
    """(geography level, crossed with sex?, breakdown) of a published row."""
    return (str(row["geography_level"]), row["sex"] != "all", str(row["breakdown"]))


def key_columns(kind: tuple[str, bool, str]) -> list[str]:
    """Person-level columns whose values, joined with "|", form a cell's key."""
    level, by_sex, breakdown = kind
    columns = [GEOGRAPHIES[level]]
    if by_sex:
        columns.append("sex")
    if breakdown != "all":
        columns.append(BREAKDOWN_COLUMNS[breakdown])
    return columns


def published_key(row: pd.Series) -> str:
    parts = [str(row["geography"])]
    if row["sex"] != "all":
        parts.append(str(row["sex"]))
    if row["breakdown"] != "all":
        parts.append(str(row["breakdown_level"]))
    return "|".join(parts)


def svy_estimates(frame: pd.DataFrame, public: pd.DataFrame) -> pd.DataFrame:
    """svy mean and SE for every (cell type, age group, measure) present in ``public``."""
    measures = sorted(str(m) for m in public["measure"].unique())
    indicators = pd.DataFrame(wg_indicators(frame, levels=True))[measures].astype("float64")
    people = frame[["psu", "stratum", "weight", "state_code", "zone", "sex", "age_group"]]
    people = people.assign(
        national="NG",
        sector=frame["sector"],
        wealth_quintile=frame["wealth_quintile"],
        prevalence_age_band=c.prevalence_age_band(frame["age"]),
    )
    data = pl.from_pandas(pd.concat([people, indicators], axis=1))
    data = data.filter(pl.col("age_group").is_not_null())
    kinds = sorted(set(public.apply(cell_type, axis=1)))
    names = {kind: f"_key{i}" for i, kind in enumerate(kinds)}
    data = data.with_columns(
        pl.concat_str([pl.col(col) for col in key_columns(kind)], separator="|").alias(name)
        for kind, name in names.items()
    )
    design = svy.Design(
        stratum="stratum",
        psu="psu",
        wgt="weight",
        singleton=svy.Singleton(svy.SingletonMethod.CENTER),
    )
    sample = svy.Sample(data, design)
    kind_of = public.apply(cell_type, axis=1)
    rows = []
    for kind, name in names.items():
        wanted = public[kind_of == kind]
        for (age, measure), _ in wanted.groupby(["age_group", "measure"]):
            est = sample.estimation.mean(
                str(measure),
                by=name,
                where=(pl.col("age_group") == age) & pl.col(name).is_not_null(),
                drop_nulls=True,
            )
            assert isinstance(est, svy.Estimate)  # one measure in, one Estimate out
            out = est.to_polars().to_pandas().rename(columns={name: "key"})
            out["kind"], out["measure"], out["age_group"] = str(kind), measure, age
            rows.append(out[["kind", "measure", "age_group", "key", "est", "se"]])
    return pd.concat(rows, ignore_index=True)


@c.safe_main
def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Cross-check published DHS cells with svy.")
    parser.add_argument("--persons", type=Path, default=PERSONS)
    parser.add_argument("--public", type=Path, nargs="+", default=list(PUBLIC))
    args = parser.parse_args(argv)

    public = pd.concat([pd.read_csv(path) for path in args.public], ignore_index=True)
    public = pd.DataFrame(public[~public["suppressed"]])
    public["kind"] = public.apply(cell_type, axis=1).map(str)
    public["key"] = public.apply(published_key, axis=1)

    ours = svy_estimates(pd.read_parquet(args.persons), public)
    ours = ours.rename(columns={"est": "svy_estimate", "se": "svy_se"})
    merged = public.merge(ours, on=["kind", "measure", "age_group", "key"], how="left")
    missing = int(merged["svy_estimate"].isna().to_numpy().sum())
    est_gap = (merged["estimate"] - merged["svy_estimate"]).abs()
    has_se = merged["se"] > 0
    se_gap = ((merged["se"] - merged["svy_se"]).abs() / merged["se"]).where(has_se)
    by_level = merged.groupby("geography_level").size().to_dict()
    c.log(
        f"{len(merged)} published DHS cells compared {by_level} "
        f"({missing} without an svy counterpart)\n"
        f"  estimate: largest absolute difference {est_gap.max():.2e}; "
        f"{int((est_gap > ESTIMATE_TOL).to_numpy().sum())} above {ESTIMATE_TOL:.0e}\n"
        f"  SE: median relative difference {se_gap.median():.2%}, largest {se_gap.max():.2%}; "
        f"{int((se_gap > SE_TOL).to_numpy().sum())} above {SE_TOL:.0%}"
    )
    worst = merged.assign(se_gap=se_gap).nlargest(5, "se_gap")
    for _, row in worst.iterrows():
        c.log(
            f"  largest SE gaps: {row['measure']} / {row['age_group']} / {row['geography']} / "
            f"{row['sex']} / {row['breakdown']}={row['breakdown_level']}: "
            f"R {row['se']:.5f}, svy {row['svy_se']:.5f}"
        )
    ok = missing == 0 and (est_gap <= ESTIMATE_TOL).all() and (se_gap.fillna(0) <= SE_TOL).all()
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
