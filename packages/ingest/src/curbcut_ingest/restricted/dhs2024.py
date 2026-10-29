"""Harmonise Nigeria DHS 2024 (NGPR8BFL, household member recode) to the common schema.

DHS 2024 asks the Washington Group Short Set of every household member aged 5+ (standard
WG-SS wording, 1-4 scale, 8 = don't know). Design (DHS Guide to Statistics): weight
``hv005 / 1e6``, PSU ``hv021``, strata ``hv023`` (state x urban/rural). Following the DHS
tables for household members, the population is the de facto one (``hv103 == 1``).
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

import pandas as pd

from curbcut_ingest.restricted import common as c
from curbcut_ingest.states import StateLookup

SOURCE = "dhs2024"
DEFAULT_INPUT = c.RESTRICTED / "dhs-2024" / "pr" / "NGPR8BFL.dta"

DOMAIN_VARS = {
    "seeing": "hdis2",
    "hearing": "hdis4",
    "communication": "hdis5",
    "cognition": "hdis6",
    "walking": "hdis7",
    "selfcare": "hdis8",
}
COLUMNS = [
    "hv001",
    "hv002",
    "hvidx",
    "hv005",
    "hv021",
    "hv023",
    "hv025",
    "hv103",
    "hv104",
    "hv105",
    "hv270",
    "shstate",
    *DOMAIN_VARS.values(),
    "hdis9",
]
WEALTH_QUINTILE = {1: "lowest", 2: "second", 3: "middle", 4: "fourth", 5: "highest"}
"""hv270 (wealth index combined): 1 poorest, 2 poorer, 3 middle, 4 richer, 5 richest
(value labels checked in the NGPR8BFL metadata, 2026-10-27)."""


def harmonise(raw: pd.DataFrame, state_labels: dict[int, str], lookup: StateLookup) -> pd.DataFrame:
    """Raw PR columns (codes) -> common schema. Pure function, tested on invented rows."""
    states = lookup.map_codes(state_labels)
    de_facto = c.to_num(raw["hv103"]) == 1
    age = c.to_num(raw["hv105"]).where(lambda a: a < 98)
    domains = pd.DataFrame({d: c.wg_scale(raw[v]) for d, v in DOMAIN_VARS.items()})
    asked = raw[list(DOMAIN_VARS.values())].notna().any(axis=1)
    keep = de_facto & asked & (age >= 5)

    out = pd.DataFrame(index=raw.index)
    out["source"] = SOURCE
    out["person_id"] = c.join_codes(SOURCE, raw["hv001"], raw["hv002"], raw["hvidx"])
    c.attach_state(out, raw["shstate"], states)
    out["sector"] = c.recode(raw["hv025"], c.SECTOR)
    out["sex"] = c.recode(raw["hv104"], c.SEX)
    out["age"] = age.astype("Int16")
    out["age_group"] = c.age_group(age)
    out["age_band"] = c.age_band(age)
    out["weight"] = c.to_num(raw["hv005"]) / 1e6
    out["stratum"] = c.join_codes(SOURCE, raw["hv023"])
    out["psu"] = c.join_codes(SOURCE, raw["hv021"])
    for domain in c.WG_DOMAINS:
        out[domain] = domains[domain]
    out["disability3"] = c.disability3(domains[list(c.WG_DOMAINS)])
    out["dhs_hdis9"] = c.wg_scale(raw["hdis9"])
    out["wealth_quintile"] = c.recode(raw["hv270"], WEALTH_QUINTILE)
    extra = [*c.WG_DOMAINS, "disability3", "dhs_hdis9", "wealth_quintile"]
    return c.finish(out[keep], extra)


@c.safe_main
def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Harmonise DHS 2024 PR to person-level Parquet.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--out-dir", type=Path, default=c.DERIVED)
    args = parser.parse_args(argv)

    c.log(f"DHS 2024: reading {len(COLUMNS)} columns from {args.input.name}")
    raw, meta = c.read_dta(args.input, COLUMNS)
    c.log(f"  rows in file: {c.masked(len(raw))}")
    frame = harmonise(raw, c.value_labels(meta, "shstate"), StateLookup.from_seeds())
    c.log(f"  de facto, aged 5+, asked the module: {c.masked(len(frame))}")
    c.report_counts("age_group", frame["age_group"])
    c.report_counts("disability3", frame["disability3"])
    c.report_counts("wealth_quintile", frame["wealth_quintile"])
    # Cross-check against DHS's own summary variable (highest level in any domain).
    own = frame["dhs_hdis9"] >= 3
    mine = frame["disability3"] == 1
    disagree = int((own.fillna(False) != mine.fillna(False)).sum())
    c.log(f"  disability3 vs hdis9>=3 disagreements: {c.masked(disagree)}")
    c.write_parquet(frame, SOURCE, args.out_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
