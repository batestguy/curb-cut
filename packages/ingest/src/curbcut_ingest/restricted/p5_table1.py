"""P5 manuscript Table 1: household characteristics by exposure (descriptive).

Run from the repo root, after ``p5_mpi --real`` has its inputs:
``uv run python -I -m curbcut_ingest.restricted.p5_table1``.

STROBE item 14a. Not part of the registered analysis (``docs/preregistration.md``): a
descriptive table of the covariates of section 3.4, in the primary analysis sample (a
non-missing primary exposure and a non-missing outcome; the outcome's values are never
read), by primary exposure. Shares and means are weighted by ``pop_wgt``, so they describe
people, like the estimand. No poverty figure is computed.

Every cell leaves through :func:`curbcut_ingest.disclosure.publish_table` (cells from fewer
than 30 households are suppressed, with complementary suppression within a characteristic),
into ``data/public/aggregates/p5_table1.csv``. Nothing else is written or printed.
"""

from __future__ import annotations

import argparse
import dataclasses
from collections.abc import Sequence

import numpy as np
import pandas as pd

from curbcut_ingest import disclosure
from curbcut_ingest.restricted import common as c
from curbcut_ingest.restricted.p5_mpi import COUNTS, load_real
from curbcut_ingest.restricted.p5_publish import MPI

DATASET = dataclasses.replace(
    MPI,
    design=(
        "P5 manuscript Table 1 (not pre-registered; descriptive): households in the "
        "primary analysis sample (non-missing primary exposure and outcome), by primary "
        "exposure; shares and means weighted by pop_wgt (person-weighted). No poverty "
        "figure."
    ),
)

FILENAME = "p5_table1.csv"
TABLE = "table1"
GROUPS = {1.0: "exposed", 0.0: "unexposed"}
MISSING = "missing"
HEAD_AGE_BANDS = ((0, 29, "under 30"), (30, 44, "30-44"), (45, 59, "45-59"), (60, 200, "60+"))
COUNT_LABELS = {
    "n_0_4": "members aged 0-4",
    "n_5": "members aged 5",
    "n_6_14": "members aged 6-14",
    "n_15_17": "members aged 15-17",
    "n_18_59": "members aged 18-59",
    "n_60_69": "members aged 60-69",
    "n_70plus": "members aged 70+",
}


def head_age_band(age: pd.Series) -> pd.Series:
    value = pd.to_numeric(age, errors="coerce")
    out = pd.Series(MISSING, index=age.index, dtype="string")
    for lo, hi, label in HEAD_AGE_BANDS:
        out[value.between(lo, hi)] = label
    return out


def categorical(frame: pd.DataFrame) -> dict[str, pd.Series]:
    return {
        "zone": frame["zone"].astype("string").fillna(MISSING),
        "sector": frame["sector"].astype("string").fillna(MISSING),
        "head_sex": frame["head_sex"].astype("string").fillna(MISSING),
        "head_age": head_age_band(frame["head_age"]),
        "head_education": frame["head_education"].astype("string").fillna(MISSING),
    }


def table1(frame: pd.DataFrame) -> pd.DataFrame:
    """The raw (ungated) cells. ``frame`` is the analysis frame of ``p5_mpi``."""
    sample = frame[frame["exposed_primary"].notna() & frame["poor"].notna()].copy()
    w = sample["pop_wgt"].astype("float64")
    group = sample["exposed_primary"].astype("float64").map(GROUPS)
    rows: list[dict[str, object]] = []
    for gvalue in GROUPS.values():
        in_group = (group == gvalue).to_numpy()
        wg = w[in_group]
        total = float(wg.sum())
        rows.append(
            {
                "characteristic": "households",
                "category": "all",
                "kind": "share",
                "group": gvalue,
                "n": int(in_group.sum()),
                "value": 1.0,
            }
        )
        for name, values in categorical(sample).items():
            vg = values[in_group]
            for category in sorted(set(values)):
                cell = (vg == category).to_numpy()
                rows.append(
                    {
                        "characteristic": name,
                        "category": category,
                        "kind": "share",
                        "group": gvalue,
                        "n": int(cell.sum()),
                        "value": float(wg[cell].sum()) / total,
                    }
                )
        size = sample[list(COUNTS)].astype("float64").sum(axis=1)
        for col, label in [*COUNT_LABELS.items(), ("hh_size", "household members, all ages")]:
            x = (size if col == "hh_size" else sample[col].astype("float64"))[in_group]
            rows.append(
                {
                    "characteristic": "age_structure",
                    "category": label,
                    "kind": "mean",
                    "group": gvalue,
                    "n": int(in_group.sum()),
                    "value": float(np.average(x, weights=wg)),
                }
            )
    out = pd.DataFrame(rows)
    out.insert(0, "table", TABLE)
    return out


@c.safe_main
def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="P5 Table 1: characteristics by exposure.")
    parser.parse_args(argv)
    if disclosure.script_commit().endswith("-dirty"):
        print("refused: commit the code first, so the manifest names a real commit")
        return 2
    frame, _, _ = load_real(c.DERIVED)
    path, entry = disclosure.publish_table(table1(frame), DATASET, FILENAME)
    print(f"wrote {path.name}: {entry['rows']} cells, {entry['suppressed_cells']} suppressed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
