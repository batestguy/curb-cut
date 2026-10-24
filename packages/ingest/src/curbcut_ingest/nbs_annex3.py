"""Copy the state x sex 2023 projections from NBS Demographic Bulletin 2023, Annex 3.

Local only: the datasheet (``data/sources/nbs-demographic-2023/Demographic Bulletin
Datasheet.xlsx``) is "All Rights Reserved" and git-ignored, so CI uses the committed seed
this writes (``packages/transform/seeds/state_population_by_sex_2023.csv``): 74 cited
figures, source National Population Commission via NBS (``docs/verification.md`` D8).

Checks before writing: 37 states, each matched through the alias seed once; males +
females = total on every row; the columns sum to the sheet's Nigeria row; and the totals
equal the ``population_2023`` already in the ``state_facts`` seed.
"""

from __future__ import annotations

import argparse
import csv
import re
from collections.abc import Sequence
from pathlib import Path

from curbcut_ingest.states import SEEDS, StateLookup

ROOT = Path(__file__).resolve().parents[4]
DEFAULT_XLSX = (
    ROOT / "data" / "sources" / "nbs-demographic-2023" / "Demographic Bulletin Datasheet.xlsx"
)
DEFAULT_OUT = SEEDS / "state_population_by_sex_2023.csv"
SHEET = "Annex 3"
SOURCE_URL = "https://microdata.nigerianstat.gov.ng/index.php/catalog/182"

_STATE_SUFFIX = re.compile(r"\s+state\s*$", re.IGNORECASE)


class Annex3Error(ValueError):
    """The sheet does not look as expected; nothing is written."""


def parse_rows(
    rows: Sequence[Sequence[object]], lookup: StateLookup
) -> tuple[dict[str, tuple[int, int, int]], tuple[int, int, int]]:
    """Sheet rows -> ({state: (males, females, total)}, Nigeria row)."""
    states: dict[str, tuple[int, int, int]] = {}
    nigeria: tuple[int, int, int] | None = None
    header_seen = False
    for row in rows:
        cells = list(row) + [None] * 4
        label = cells[0]
        if not header_seen:
            header_seen = label == "State" and cells[1] == "Males"
            continue
        if not isinstance(label, str) or not all(isinstance(v, int) for v in cells[1:4]):
            if states:
                break  # end of the table
            continue
        values = (int(cells[1]), int(cells[2]), int(cells[3]))  # type: ignore[arg-type]
        if label.strip().lower() == "nigeria":
            nigeria = values
            break
        state = lookup.resolve(_STATE_SUFFIX.sub("", label)).state
        if state in states:
            raise Annex3Error(f"{state} appears twice")
        states[state] = values
    if nigeria is None or len(states) != len(lookup.states):
        raise Annex3Error(f"expected 37 states and a Nigeria row, got {len(states)}")
    for state, (m, f, t) in states.items():
        if m + f != t:
            raise Annex3Error(f"{state}: males + females != total")
    sums = tuple(sum(v[i] for v in states.values()) for i in range(3))
    if sums != nigeria:
        raise Annex3Error("state rows do not sum to the Nigeria row")
    return states, nigeria


def check_against_state_facts(states: dict[str, tuple[int, int, int]], seeds: Path) -> None:
    with (seeds / "state_facts.csv").open(encoding="utf-8", newline="") as f:
        facts = {r["state"]: int(r["population_2023"]) for r in csv.DictReader(f)}
    for state, (_, _, total) in states.items():
        if facts.get(state) != total:
            raise Annex3Error(f"{state}: total differs from state_facts.population_2023")


def write_seed(states: dict[str, tuple[int, int, int]], path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(["state", "sex", "population_2023"])
        for state in sorted(states):
            males, females, _ = states[state]
            writer.writerow([state, "male", males])
            writer.writerow([state, "female", females])


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="NBS Annex 3 (state x sex 2023) to a seed.")
    parser.add_argument("--xlsx", type=Path, default=DEFAULT_XLSX)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)

    import openpyxl

    workbook = openpyxl.load_workbook(args.xlsx, read_only=True, data_only=True)
    rows = list(workbook[SHEET].iter_rows(values_only=True))
    lookup = StateLookup.from_seeds()
    states, nigeria = parse_rows(rows, lookup)
    check_against_state_facts(states, SEEDS)
    write_seed(states, args.out)
    print(f"wrote {2 * len(states)} rows to {args.out.name}; Nigeria total {nigeria[2]:,}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
