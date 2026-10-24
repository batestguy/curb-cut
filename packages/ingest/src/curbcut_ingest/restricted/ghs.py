"""Harmonise GHS-Panel W4 (2018/19) and W5 (2023/24) disability questions.

Both waves ask the six WG-SS questions with the WG wording and 1-4 scale (W4 post-harvest
``sect4a``, ``s4aq23``-``s4aq33``; W5 post-planting ``sect3``, ``s3q23``-``s3q28``). W4 also
codes -1 "too young"; that, and any other code outside 1-4, is missing.

GHS is representative only nationally and by zone, so **no state-level output is ever
produced from it** (the person-level file keeps the state for design checks only).

Design: cross-section household weight (W4 ``wt_wave4``, W5 ``wt_cross_wave5``) applied to
each member; strata ``strata`` (the original sampling strata, labelled by zone); PSU
``cluster`` (the original EA; ``ea`` codes repeat across LGAs, ``cluster`` is unique).
Households without a weight are dropped. Ages from the household roster of the same visit.
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from curbcut_ingest.restricted import common as c
from curbcut_ingest.states import StateLookup


@dataclass(frozen=True)
class Wave:
    source: str
    disability_file: Path
    roster_file: Path
    cover_file: Path
    domains: dict[str, str]
    age: str
    weight: str


W4_DIR = c.RESTRICTED / "ghs-w4"
W5_DIR = c.RESTRICTED / "ghs-w5" / "Post Planting Wave 5" / "Household"

WAVES = {
    "w4": Wave(
        source="ghs_w4",
        disability_file=W4_DIR / "sect4a_harvestw4.dta",
        roster_file=W4_DIR / "sect1_harvestw4.dta",
        cover_file=W4_DIR / "secta_harvestw4.dta",
        domains={
            "seeing": "s4aq23",
            "hearing": "s4aq25",
            "walking": "s4aq27",
            "cognition": "s4aq29",
            "selfcare": "s4aq31",
            "communication": "s4aq33",
        },
        age="s1q4",
        weight="wt_wave4",
    ),
    "w5": Wave(
        source="ghs_w5",
        disability_file=W5_DIR / "sect3_plantingw5.dta",
        roster_file=W5_DIR / "sect1_plantingw5.dta",
        cover_file=W5_DIR / "secta_plantingw5.dta",
        domains={
            "seeing": "s3q23",
            "hearing": "s3q24",
            "walking": "s3q25",
            "cognition": "s3q26",
            "selfcare": "s3q27",
            "communication": "s3q28",
        },
        age="s1q6",
        weight="wt_cross_wave5",
    ),
}
COVER_COLUMNS = ["hhid", "state", "sector", "cluster", "strata"]


def harmonise(
    wave: Wave,
    disability: pd.DataFrame,
    roster: pd.DataFrame,
    cover: pd.DataFrame,
    state_labels: dict[int, str],
    lookup: StateLookup,
) -> pd.DataFrame:
    """Raw wave files (codes) -> common schema. Pure; tested on invented rows."""
    states = lookup.map_codes(state_labels)
    people = disability.merge(roster, on=["hhid", "indiv"], how="inner", validate="one_to_one")
    people = people.merge(cover, on="hhid", how="inner", validate="many_to_one")
    age = c.to_num(people[wave.age])
    weight = c.to_num(people[wave.weight])
    domains = pd.DataFrame({d: c.wg_scale(people[v]) for d, v in wave.domains.items()})
    asked = people[list(wave.domains.values())].notna().any(axis=1)

    out = pd.DataFrame(index=people.index)
    out["source"] = wave.source
    out["person_id"] = c.join_codes(wave.source, people["hhid"], people["indiv"])
    c.attach_state(out, people["state"], states)
    out["sector"] = c.recode(people["sector"], c.SECTOR)
    out["sex"] = c.recode(people["s1q2"], c.SEX)
    out["age"] = age.astype("Int16")
    out["age_group"] = c.age_group(age)
    out["age_band"] = c.age_band(age)
    out["weight"] = weight
    out["stratum"] = c.join_codes(wave.source, people["strata"])
    out["psu"] = c.join_codes(wave.source, people["cluster"])
    for domain in c.WG_DOMAINS:
        out[domain] = domains[domain]
    out["disability3"] = c.disability3(domains[list(c.WG_DOMAINS)])
    keep = asked & (age >= 5) & weight.notna() & (weight > 0)
    return c.finish(out[keep], [*c.WG_DOMAINS, "disability3"])


def run(wave: Wave, out_dir: Path) -> Path:
    c.log(f"GHS {wave.source}: reading named columns only")
    disability, _ = c.read_dta(wave.disability_file, ["hhid", "indiv", *wave.domains.values()])
    roster, _ = c.read_dta(wave.roster_file, ["hhid", "indiv", "s1q2", wave.age])
    cover, meta = c.read_dta(wave.cover_file, [*COVER_COLUMNS, wave.weight])
    c.log(f"  disability rows: {c.masked(len(disability))}")
    frame = harmonise(
        wave, disability, roster, cover, c.value_labels(meta, "state"), StateLookup.from_seeds()
    )
    c.log(f"  asked, aged 5+, with a weight: {c.masked(len(frame))}")
    c.report_counts("age_group", frame["age_group"])
    c.report_counts("disability3", frame["disability3"])
    return c.write_parquet(frame, wave.source, out_dir)


@c.safe_main
def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Harmonise GHS-Panel W4/W5 to Parquet.")
    parser.add_argument("--waves", nargs="+", choices=sorted(WAVES), default=sorted(WAVES))
    parser.add_argument("--out-dir", type=Path, default=c.DERIVED)
    args = parser.parse_args(argv)
    for key in args.waves:
        run(WAVES[key], args.out_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
