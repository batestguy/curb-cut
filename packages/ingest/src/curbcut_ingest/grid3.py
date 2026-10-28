"""Health facilities per state from GRID3 NGA - Health Facilities v2.0 (P4a step 3).

The source is a CC BY 4.0 GeoPackage from CIESIN, Columbia University (``docs/verification.md``
D57), kept git-ignored in ``data/sources/grid3/``. Its SHA-256 is checked before anything is
read. Facilities are counted by the dataset's own ``state`` attribute (every record has one,
and every record has coordinates), resolved through the repo's state seeds, so no spatial join
is needed. The rate uses the NBS 2023 Annex 3 population (seed ``state_facts``, D14).

Only the 37-row aggregate is committed: ``data/public/spatial/facilities_state.csv``. It is a
measure of general health-facility supply. It is not a measure of disability services.

Run (local only; needs the GeoPackage): ``uv run python -I -m curbcut_ingest.grid3``.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import sqlite3
import sys
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path

from curbcut_ingest.states import StateLookup, UnknownStateError

ROOT = Path(__file__).resolve().parents[4]
SOURCE = ROOT / "data" / "sources" / "grid3" / "NGA_health_facilities_v2_0.gpkg"
SOURCE_SHA256 = "cd4b90f804c22a473a755d488ef92703fc165a3063e205a8983adac218087318"
LAYER = "NGA_health_facilities_v2_0"
OUT = ROOT / "data" / "public" / "spatial" / "facilities_state.csv"

CSV_COLUMNS = [
    "state",
    "state_code",
    "population_2023",
    "facilities",
    "facilities_public",
    "facilities_ownership_unknown",
    "facilities_primary",
    "facilities_secondary_tertiary",
    "facilities_per_100k",
]


class Grid3Error(ValueError):
    """The source file or its contents failed a check."""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_records(path: Path) -> list[tuple[str, str, str]]:
    """(state, ownership, facility_level) for every facility in the GeoPackage."""
    uri = f"{path.resolve().as_uri()}?mode=ro"
    with sqlite3.connect(uri, uri=True) as con:
        rows = con.execute(f'SELECT state, ownership, facility_level FROM "{LAYER}"').fetchall()
    return [(str(s), str(o), str(lv)) for s, o, lv in rows]


def aggregate(
    records: Iterable[tuple[str, str, str]],
    lookup: StateLookup,
    population: Mapping[str, int],
) -> list[dict[str, object]]:
    """Count facilities per canonical state; raise unless all states are covered.

    Pure apart from its inputs (tested on invented records).
    """
    total: Counter[str] = Counter()
    public: Counter[str] = Counter()
    unknown: Counter[str] = Counter()
    primary: Counter[str] = Counter()
    higher: Counter[str] = Counter()
    for state_label, ownership, level in records:
        try:
            state = lookup.resolve(state_label).state
        except UnknownStateError as exc:
            raise Grid3Error(str(exc)) from None
        total[state] += 1
        public[state] += ownership == "Public"
        unknown[state] += ownership == "Unknown"
        primary[state] += level == "Primary"
        higher[state] += level in ("Secondary", "Tertiary")
    missing = sorted(set(lookup.states) - set(total))
    if missing:
        raise Grid3Error(f"no facilities for {missing}")
    if set(population) != set(lookup.states):
        raise Grid3Error(
            f"population differs from states: {sorted(set(population) ^ set(lookup.states))}"
        )
    rows: list[dict[str, object]] = []
    for name in sorted(lookup.states):
        pop = population[name]
        if pop <= 0:
            raise Grid3Error(f"{name}: population {pop}")
        rows.append(
            {
                "state": name,
                "state_code": lookup.states[name].state_code,
                "population_2023": pop,
                "facilities": total[name],
                "facilities_public": public[name],
                "facilities_ownership_unknown": unknown[name],
                "facilities_primary": primary[name],
                "facilities_secondary_tertiary": higher[name],
                "facilities_per_100k": round(total[name] / pop * 100_000, 4),
            }
        )
    return rows


def read_population(seeds: Path) -> dict[str, int]:
    with (seeds / "state_facts.csv").open(encoding="utf-8", newline="") as f:
        return {r["state"]: int(r["population_2023"]) for r in csv.DictReader(f)}


def write_csv(rows: Sequence[Mapping[str, object]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main(argv: Sequence[str] | None = None) -> int:
    from curbcut_ingest.states import SEEDS

    parser = argparse.ArgumentParser(description="Count GRID3 health facilities per state.")
    parser.add_argument("--source", type=Path, default=SOURCE)
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args(argv)
    try:
        if not args.source.is_file():
            raise Grid3Error(f"missing source file {args.source}")
        found = sha256(args.source)
        if found != SOURCE_SHA256:
            raise Grid3Error(f"{args.source.name}: SHA-256 {found} differs from {SOURCE_SHA256}")
        lookup = StateLookup.from_seeds()
        rows = aggregate(read_records(args.source), lookup, read_population(SEEDS))
    except Grid3Error as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    write_csv(rows, args.out)
    total = sum(int(str(r["facilities"])) for r in rows)
    print(f"grid3: wrote {len(rows)} states, {total} facilities")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
