"""Build the state-level Fay-Herriot covariates frozen in ``docs/fay-herriot-covariates.md``.

Writes ``data/public/covariates/state_covariates.csv`` (37 rows, one per state) and
``manifest.json`` beside it. Nothing here touches the outcome: no disability figure is read,
joined or compared (the selection stays blind until the model is fitted).

- C1 ``c1_share_60plus``: WorldPop "Nigeria 100m Age structures", constrained, UN-adjusted,
  2020 (doi:10.5258/SOTON/WP00699). Zonal sums of the 36 age-sex rasters over the committed
  geoBoundaries ADM1 polygons; bands 60-80+ of both sexes over all bands. ``docs/verification.md``
  D50.
- C2 ``c2_urban_share``: JRC GHSL GHS-SMOD R2023A (V2-0) and GHS-POP R2023A (V1-0), 2020
  epoch, 1 km Mollweide. Share of GHS-POP in SMOD classes 21-30 (D51).
- C3 ``c3_mpi_headcount``: NBS "Nigeria Multidimensional Poverty Index (2022)", Table D6,
  incidence H as a proportion, read from the committed transcription
  ``nbs_mpi2022_table_d6.csv`` and checked here (D52).
- C4 (literacy of women 15-24) is **not built**: the MICS6 2021 report has no state table
  for that age group (D53). It waits on the author's decision.
- C5 ``c5_log_density``: natural log of NBS 2023 Annex 3 population (seed ``state_facts``)
  per km2 of the geoBoundaries polygon, area computed in EPSG:6933 (D54).

Two more columns are **benchmark weights for the FH step, not covariates**:
``wp2020_pop_total`` (all bands) and ``wp2020_pop_18plus`` (bands 20-80+ plus 2/5 of the 15-19
band, which assumes ages 15-19 are evenly spread), both sexes, from the same zonal sums.

The rasters and PDFs stay git-ignored in ``data/sources/covariates/``; every file's SHA-256
is checked against the committed ``source_sha256.txt`` before anything is computed.

Run (local only; about 2 GB of rasters): ``uv run python -I -m curbcut_ingest.covariates``.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import math
import sys
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from curbcut_ingest.states import SEEDS, StateLookup

ROOT = Path(__file__).resolve().parents[4]
SOURCES = ROOT / "data" / "sources" / "covariates"
PUBLIC = ROOT / "data" / "public" / "covariates"
GEOJSON = ROOT / "data" / "public" / "geoboundaries" / "geoBoundaries-NGA-ADM1_simplified.geojson"
MPI_TABLE = PUBLIC / "nbs_mpi2022_table_d6.csv"
OUT_CSV = PUBLIC / "state_covariates.csv"
OUT_MANIFEST = PUBLIC / "manifest.json"

WORLDPOP_DIR = "worldpop_agesex_2020"
WORLDPOP_URL = (
    "https://data.worldpop.org/GIS/AgeSex_structures/Global_2000_2020_Constrained_UNadj/2020/NGA/"
)
AGES = (0, 1, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75, 80)
"""WorldPop band lower bounds: 0 = under 1, 1 = 1-4, then 5-year groups, 80 = 80 and over."""
AGES_60_PLUS = (60, 65, 70, 75, 80)
AGES_20_PLUS = tuple(a for a in AGES if a >= 20)
SHARE_OF_15_19_AGED_18_19 = 2 / 5
"""Ages 18-19 as a share of the 15-19 band, assuming single years are evenly spread."""

GHSL_DIR = "ghsl_r2023a"
GHSL_SMOD = "GHS_SMOD_E2020_GLOBE_R2023A_54009_1000_V2_0.tif"
GHSL_POP = "GHS_POP_E2020_GLOBE_R2023A_54009_1000_V1_0.tif"
GHSL_URL = "https://jrc-ghsl.s3.amazonaws.com/"
URBAN_CLASSES = (21, 30)
"""Degree of Urbanisation level 1: 21 suburban/peri-urban, 22 semi-dense urban cluster,
23 dense urban cluster, 30 urban centre (inclusive range)."""

AREA_CRS = "EPSG:6933"
"""WGS 84 / NSIDC EASE-Grid 2.0 Global: cylindrical equal-area, so planar area is true area."""

MPI_NATIONAL_H = 62.9
"""National incidence H (%), Table D4 (printed p. 99) of the same report."""
MPI_PRESS_RANGE = {"Ondo": 27.2, "Sokoto": 90.5}
"""Lowest and highest state H (%) in the press release (rounded there to 27% and 91%)."""

HASHES = PUBLIC / "source_sha256.txt"
"""Committed ``sha256sum`` list of every downloaded file, paths relative to ``SOURCES``."""

CSV_COLUMNS = [
    "state",
    "state_code",
    "c1_share_60plus",
    "c2_urban_share",
    "c3_mpi_headcount",
    "c5_log_density",
    "population_2023",
    "area_km2",
    "wp2020_pop_total",
    "wp2020_pop_18plus",
]


class CovariateError(ValueError):
    """A source or a result failed a check; nothing is written."""


@dataclass(frozen=True)
class StateShape:
    state: str
    state_code: str
    geometry: dict[str, Any]


# --- inputs ------------------------------------------------------------------


def worldpop_files() -> dict[str, str]:
    """Relative path of every WorldPop band, keyed by ``<sex>_<age>``."""
    return {
        f"{sex}_{age}": f"{WORLDPOP_DIR}/nga_{sex}_{age}_2020_constrained_UNadj.tif"
        for sex in ("f", "m")
        for age in AGES
    }


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_hashes(path: Path) -> dict[str, str]:
    """``sha256sum`` lines (``<hex>  <relative path>``) -> {path: hex}."""
    expected: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            digest, rel = line.split(maxsplit=1)
            expected[rel.strip()] = digest
    return expected


def check_hashes(sources: Path, expected: Mapping[str, str]) -> dict[str, str]:
    """Hash every expected file; raise if one is missing or differs."""
    rasters = {*worldpop_files().values(), f"{GHSL_DIR}/{GHSL_SMOD}", f"{GHSL_DIR}/{GHSL_POP}"}
    if not rasters <= set(expected):
        raise CovariateError(f"no expected hash for {sorted(rasters - set(expected))}")
    found: dict[str, str] = {}
    for rel, want in sorted(expected.items()):
        path = sources / rel
        if not path.is_file():
            raise CovariateError(f"missing source file {rel}")
        found[rel] = sha256(path)
        if found[rel] != want:
            raise CovariateError(f"{rel}: SHA-256 {found[rel]} differs from {want}")
    return found


def load_shapes(geojson: Mapping[str, Any], lookup: StateLookup) -> list[StateShape]:
    """geoBoundaries features -> canonical states; each must match once, ISO codes agree."""
    shapes: dict[str, StateShape] = {}
    for feature in geojson["features"]:
        props = feature["properties"]
        state = lookup.resolve(props["shapeName"])
        if props.get("shapeISO") != state.state_code:
            raise CovariateError(f"{props['shapeName']}: shapeISO differs from dim_states")
        if state.state in shapes:
            raise CovariateError(f"{state.state} has two polygons")
        shapes[state.state] = StateShape(state.state, state.state_code, feature["geometry"])
    if set(shapes) != set(lookup.states):
        raise CovariateError(f"missing polygons: {sorted(set(lookup.states) - set(shapes))}")
    return [shapes[s] for s in sorted(shapes)]


def read_population(seeds: Path = SEEDS) -> dict[str, int]:
    with (seeds / "state_facts.csv").open(encoding="utf-8", newline="") as f:
        return {r["state"]: int(r["population_2023"]) for r in csv.DictReader(f)}


def read_mpi_table(path: Path, lookup: StateLookup) -> dict[str, dict[str, float]]:
    """Read the Table D6 transcription and check it (pure apart from the read; tested)."""
    with path.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    table: dict[str, dict[str, float]] = {}
    for row in rows:
        state = lookup.resolve(row["state"]).state
        if state in table:
            raise CovariateError(f"MPI table: {state} appears twice")
        table[state] = {k: float(v) for k, v in row.items() if k != "state"}
    check_mpi_table(table, set(lookup.states))
    return table


def check_mpi_table(table: Mapping[str, Mapping[str, float]], states: set[str]) -> None:
    if set(table) != states:
        raise CovariateError(f"MPI table: states differ: {sorted(states ^ set(table))}")
    for state, r in table.items():
        # MPI = H x A; all three are printed rounded, so allow the rounding error.
        if abs(r["h_pct"] * r["a_pct"] / 1e4 - r["mpi"]) > 0.0015:
            raise CovariateError(f"MPI table: {state}: MPI != H x A")
        for name in ("mpi", "h", "a"):
            value = r["mpi"] if name == "mpi" else r[f"{name}_pct"]
            if not r[f"{name}_ci_low"] <= value <= r[f"{name}_ci_high"]:
                raise CovariateError(f"MPI table: {state}: {name} outside its CI")
    h = {s: r["h_pct"] for s, r in table.items()}
    if min(h, key=h.__getitem__) != "Ondo" or max(h, key=h.__getitem__) != "Sokoto":
        raise CovariateError("MPI table: lowest/highest H are not Ondo/Sokoto")
    for state, value in MPI_PRESS_RANGE.items():
        if h[state] != value:
            raise CovariateError(f"MPI table: {state} H {h[state]} != {value}")
    shares = sum(r["population_share_pct"] for r in table.values())
    weighted = sum(r["h_pct"] * r["population_share_pct"] for r in table.values()) / shares
    # Population shares are printed to 0.1 point, so the weighted mean is approximate.
    if abs(weighted - MPI_NATIONAL_H) > 1.0:
        raise CovariateError(f"MPI table: share-weighted H {weighted:.1f} far from national")


# --- geometry ------------------------------------------------------------------


def ring_area(ring: Sequence[Sequence[float]]) -> float:
    """Planar shoelace area (absolute) of a closed or open ring."""
    total = 0.0
    for (x1, y1), (x2, y2) in zip(ring, [*ring[1:], ring[0]], strict=True):
        total += x1 * y2 - x2 * y1
    return abs(total) / 2


def polygon_area(geometry: Mapping[str, Any]) -> float:
    """Planar area of a GeoJSON Polygon or MultiPolygon (holes subtracted)."""
    if geometry["type"] == "Polygon":
        polygons = [geometry["coordinates"]]
    elif geometry["type"] == "MultiPolygon":
        polygons = geometry["coordinates"]
    else:
        raise CovariateError(f"unexpected geometry type {geometry['type']}")
    return sum(ring_area(p[0]) - sum(ring_area(h) for h in p[1:]) for p in polygons)


def areas_km2(shapes: Sequence[StateShape]) -> dict[str, float]:
    from rasterio.warp import transform_geom

    return {
        s.state: polygon_area(transform_geom("EPSG:4326", AREA_CRS, s.geometry)) / 1e6
        for s in shapes
    }


# --- zonal sums ------------------------------------------------------------------


def zone_grid(
    shapes: Sequence[StateShape], crs: Any, transform: Any, shape: tuple[int, int]
) -> np.ndarray:
    """Raster of zone numbers (1..37 in ``shapes`` order, 0 = outside) on the given grid.

    A cell belongs to the polygon containing its centre (rasterio's default rule)."""
    from rasterio.features import rasterize
    from rasterio.warp import transform_geom

    pairs = [(transform_geom("EPSG:4326", crs, s.geometry), i + 1) for i, s in enumerate(shapes)]
    return rasterize(pairs, out_shape=shape, transform=transform, fill=0, dtype="uint8")


def zonal_sum(values: np.ndarray, zones: np.ndarray, n_zones: int) -> np.ndarray:
    """Sum of ``values`` per zone 0..n_zones (zone 0 = outside every polygon)."""
    return np.bincount(zones.ravel(), weights=values.ravel(), minlength=n_zones + 1)


def worldpop_sums(
    sources: Path, shapes: Sequence[StateShape], rows_per_chunk: int = 1024
) -> tuple[dict[str, np.ndarray], np.ndarray]:
    """Zone sums (index 0 = outside polygons) of each WorldPop band, and the raster totals."""
    import rasterio
    from rasterio.windows import Window

    files = worldpop_files()
    zones: np.ndarray | None = None
    grid: tuple[Any, ...] | None = None
    sums: dict[str, np.ndarray] = {}
    totals = np.zeros(len(files))
    for k, (band, rel) in enumerate(files.items()):
        with rasterio.open(sources / rel) as src:
            this_grid = (src.crs, src.transform, src.shape)
            if zones is None:
                grid = this_grid
                zones = zone_grid(shapes, src.crs, src.transform, src.shape)
            elif this_grid != grid:
                raise CovariateError(f"{rel} is on a different grid")
            acc = np.zeros(len(shapes) + 1)
            for row in range(0, src.height, rows_per_chunk):
                h = min(rows_per_chunk, src.height - row)
                data = src.read(
                    1, window=Window.from_slices((row, row + h), (0, src.width)), masked=True
                )
                values = data.filled(0).astype(np.float64)
                acc += zonal_sum(values, zones[row : row + h], len(shapes))
            sums[band] = acc
            totals[k] = acc.sum()
        print(f"  {rel}: {acc.sum():,.0f}", file=sys.stderr)
    return sums, totals


def ghsl_sums(sources: Path, shapes: Sequence[StateShape]) -> tuple[np.ndarray, np.ndarray]:
    """GHS-POP 2020 per zone: (all cells, cells in SMOD classes 21-30)."""
    import rasterio
    from rasterio.features import bounds
    from rasterio.warp import transform_geom
    from rasterio.windows import Window, from_bounds

    with (
        rasterio.open(sources / GHSL_DIR / GHSL_SMOD) as smod,
        rasterio.open(sources / GHSL_DIR / GHSL_POP) as pop,
    ):
        if (smod.crs, smod.transform, smod.shape) != (pop.crs, pop.transform, pop.shape):
            raise CovariateError("GHS-SMOD and GHS-POP grids differ")
        boxes = [bounds(transform_geom("EPSG:4326", smod.crs, s.geometry)) for s in shapes]
        left, bottom = min(b[0] for b in boxes), min(b[1] for b in boxes)
        right, top = max(b[2] for b in boxes), max(b[3] for b in boxes)
        window = (
            from_bounds(left, bottom, right, top, smod.transform)
            .round_offsets(op="floor")
            .round_lengths(op="ceil")
        )
        window = window.intersection(Window.from_slices((0, smod.height), (0, smod.width)))
        classes = smod.read(1, window=window)
        people = pop.read(1, window=window, masked=True).filled(0).astype(np.float64)
        people[people < 0] = 0
        zones = zone_grid(
            shapes, smod.crs, smod.window_transform(window), (classes.shape[0], classes.shape[1])
        )
    urban = (classes >= URBAN_CLASSES[0]) & (classes <= URBAN_CLASSES[1])
    total = zonal_sum(people, zones, len(shapes))
    in_urban = zonal_sum(np.where(urban, people, 0.0), zones, len(shapes))
    return total, in_urban


# --- assembly ------------------------------------------------------------------


def assemble(
    shapes: Sequence[StateShape],
    wp: Mapping[str, np.ndarray],
    ghs_total: np.ndarray,
    ghs_urban: np.ndarray,
    mpi: Mapping[str, Mapping[str, float]],
    population: Mapping[str, int],
    area: Mapping[str, float],
) -> list[dict[str, Any]]:
    """One row per state (pure; tested). Zone index i+1 is ``shapes[i]``."""
    rows = []
    for i, s in enumerate(shapes):
        z = i + 1
        total = sum(float(v[z]) for v in wp.values())
        aged_60 = sum(float(wp[f"{sex}_{a}"][z]) for sex in ("f", "m") for a in AGES_60_PLUS)
        aged_20 = sum(float(wp[f"{sex}_{a}"][z]) for sex in ("f", "m") for a in AGES_20_PLUS)
        aged_15_19 = sum(float(wp[f"{sex}_15"][z]) for sex in ("f", "m"))
        if total <= 0 or ghs_total[z] <= 0:
            raise CovariateError(f"{s.state}: no population inside its polygon")
        rows.append(
            {
                "state": s.state,
                "state_code": s.state_code,
                "c1_share_60plus": round(aged_60 / total, 6),
                "c2_urban_share": round(float(ghs_urban[z] / ghs_total[z]), 6),
                "c3_mpi_headcount": round(mpi[s.state]["h_pct"] / 100, 3),
                "c5_log_density": round(math.log(population[s.state] / area[s.state]), 6),
                "population_2023": population[s.state],
                "area_km2": round(area[s.state], 1),
                "wp2020_pop_total": round(total),
                "wp2020_pop_18plus": round(aged_20 + SHARE_OF_15_19_AGED_18_19 * aged_15_19),
            }
        )
    check_rows(rows)
    return rows


def check_rows(rows: Sequence[Mapping[str, Any]]) -> None:
    if len(rows) != 37:
        raise CovariateError(f"expected 37 rows, got {len(rows)}")
    for r in rows:
        for col in ("c1_share_60plus", "c2_urban_share", "c3_mpi_headcount"):
            if not 0 <= r[col] <= 1:
                raise CovariateError(f"{r['state']}: {col} {r[col]} outside [0, 1]")
        if not 0 < r["wp2020_pop_18plus"] < r["wp2020_pop_total"]:
            raise CovariateError(f"{r['state']}: 18+ population not below the total")
    densest = max(rows, key=lambda r: r["c5_log_density"])["state"]
    if densest != "Lagos":
        raise CovariateError(f"densest state is {densest}, expected Lagos")


def write_csv(rows: Iterable[Mapping[str, Any]], path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the FH state covariates (C1-C3, C5).")
    parser.add_argument("--sources", type=Path, default=SOURCES)
    parser.add_argument("--out", type=Path, default=OUT_CSV)
    parser.add_argument("--manifest", type=Path, default=OUT_MANIFEST)
    args = parser.parse_args(argv)

    try:
        hashes = check_hashes(args.sources, read_hashes(HASHES))
        lookup = StateLookup.from_seeds()
        with GEOJSON.open(encoding="utf-8") as f:
            shapes = load_shapes(json.load(f), lookup)
        mpi = read_mpi_table(MPI_TABLE, lookup)
        population = read_population()
        area = areas_km2(shapes)
        wp, wp_totals = worldpop_sums(args.sources, shapes)
        ghs_total, ghs_urban = ghsl_sums(args.sources, shapes)
        rows = assemble(shapes, wp, ghs_total, ghs_urban, mpi, population, area)
    except CovariateError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    wp_inside = sum(float(v[1:].sum()) for v in wp.values())
    manifest = {
        "built_on": dt.date.today().isoformat(),
        "rows": len(rows),
        "source_sha256_checked": len(hashes),
        "worldpop_url": WORLDPOP_URL,
        "ghsl_url": GHSL_URL,
        "mpi_table": MPI_TABLE.name,
        "mpi_table_sha256": sha256(MPI_TABLE),
        "geoboundaries_sha256": sha256(GEOJSON),
        "checks": {
            "worldpop_raster_total": round(float(wp_totals.sum())),
            "worldpop_inside_polygons": round(wp_inside),
            "worldpop_outside_polygons_share": round(1 - wp_inside / float(wp_totals.sum()), 6),
            "ghsl_pop_inside_polygons": round(float(ghs_total[1:].sum())),
            "area_km2_total": round(sum(area.values()), 1),
        },
    }
    write_csv(rows, args.out)
    with args.manifest.open("w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(manifest, indent=2) + "\n")
    for r in rows:
        print(",".join(str(r[c]) for c in CSV_COLUMNS))
    print(json.dumps(manifest["checks"], indent=2))
    print(f"wrote {len(rows)} rows to {args.out.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
