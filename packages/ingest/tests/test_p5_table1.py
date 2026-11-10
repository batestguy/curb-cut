"""P5 Table 1 on a small invented analysis frame (no real data)."""

from __future__ import annotations

import pandas as pd
import pytest
from curbcut_ingest.restricted import p5_table1 as t
from curbcut_ingest.restricted.p5_mpi import COUNTS


def frame() -> pd.DataFrame:
    n = 8
    out = pd.DataFrame(
        {
            "zone": ["NC", "NC", "SW", "SW", "NC", "SW", "NC", "SW"],
            "sector": ["urban", "rural"] * 4,
            "head_sex": ["male", "female", "male", None, "male", "male", "female", "male"],
            "head_age": [25, 35, 50, 70, None, 40, 61, 33],
            "head_education": [
                "none",
                "primary",
                "higher",
                "none",
                None,
                "none",
                "primary",
                "none",
            ],
            "pop_wgt": [1.0, 2.0, 1.0, 1.0, 3.0, 1.0, 1.0, 2.0],
            "exposed_primary": [1.0, 1.0, 1.0, 0.0, 0.0, 0.0, 0.0, None],
            "poor": [1.0, 0.0, None, 1.0, 0.0, 1.0, 0.0, 1.0],
        }
    )
    for col in COUNTS:
        out[col] = [1.0] * n
    return out


def test_table1_cells() -> None:
    raw = t.table1(frame())
    exposed = raw[raw["group"] == "exposed"]
    # Sample: exposure and outcome present -> 2 exposed, 4 unexposed households.
    assert exposed.loc[exposed["characteristic"] == "households", "n"].item() == 2
    assert (
        raw.loc[(raw["group"] == "unexposed") & (raw["characteristic"] == "households"), "n"].item()
        == 4
    )
    sector = exposed[exposed["characteristic"] == "sector"].set_index("category")["value"]
    assert sector["urban"] == pytest.approx(1 / 3)  # weights 1 (urban) and 2 (rural)
    for (_, _), part in raw[raw["kind"] == "share"].groupby(["characteristic", "group"]):
        assert part["value"].sum() == pytest.approx(1.0)
    ages = raw[raw["characteristic"] == "head_age"]["category"]
    assert set(ages) <= {"under 30", "30-44", "45-59", "60+", "missing"}
    size = raw[raw["category"] == "household members, all ages"]["value"]
    assert (size == len(COUNTS)).all()
