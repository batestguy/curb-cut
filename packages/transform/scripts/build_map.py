"""Build the state locator map's SVG paths from the committed geoBoundaries GeoJSON.

Run from the repo root (no network needed; the GeoJSON is committed):
``uv run python packages/transform/scripts/build_map.py``.

Writes ``site/public/data/nigeria-states.json``: an SVG ``viewBox`` and one path per state,
keyed by ISO 3166-2 code (as in ``dim_states``). The map is an orientation graphic, not a
data chart. State names are matched through the ``state_name_aliases`` seed, with the same
normalisation as the ``normalise_state_key`` dbt macro, and the build fails unless all 37
states match and each matched code agrees with geoBoundaries' own ``shapeISO``.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SEEDS = ROOT / "packages" / "transform" / "seeds"
DEFAULT_GEOJSON = (
    ROOT / "data" / "public" / "geoboundaries" / "geoBoundaries-NGA-ADM1_simplified.geojson"
)
DEFAULT_OUT = ROOT / "site" / "public" / "data" / "nigeria-states.json"

WIDTH = 600  # SVG user units; the page scales the map to its container
LAT0 = 9.0  # equirectangular projection centred on Nigeria's mid-latitude
TOLERANCE = 0.5  # Douglas-Peucker tolerance in SVG units (under a pixel at card size)
SMALL_STATE = 3600  # states whose bounding box is under this area (SVG units²) get a ring
RING_MAX = 36  # largest ring radius (Lagos is long and thin)
PAD = 16  # margin round the map so rings at the coast and borders stay inside the viewBox
ATTRIBUTION = "Boundaries: geoBoundaries (CC BY 4.0), gbOpen NGA ADM1, source GRID3 2022"

Ring = list[tuple[float, float]]


def normalise_state_key(name: str) -> str:
    """Python twin of the normalise_state_key dbt macro."""
    return re.sub(r"[^A-Za-z]+", " ", name).strip().lower()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def state_lookup(seeds: Path) -> tuple[dict[str, str], dict[str, str]]:
    """Return (normalised name -> canonical state, canonical state -> ISO code)."""
    codes = {r["state"]: r["state_code"] for r in read_csv(seeds / "dim_states.csv")}
    keys = {normalise_state_key(s): s for s in codes}
    for row in read_csv(seeds / "state_name_aliases.csv"):
        keys[normalise_state_key(row["alias"])] = row["state"]
    return keys, codes


def polygons(geometry: dict) -> list[list[Ring]]:
    if geometry["type"] == "Polygon":
        return [geometry["coordinates"]]
    if geometry["type"] == "MultiPolygon":
        return geometry["coordinates"]
    raise ValueError(f"unexpected geometry type {geometry['type']}")


def simplify(points: list[tuple[float, float]], tolerance: float) -> list[tuple[float, float]]:
    """Douglas-Peucker: keep only points further than ``tolerance`` from the simplified line."""
    if len(points) < 3:
        return points
    keep = [False] * len(points)
    keep[0] = keep[-1] = True
    stack = [(0, len(points) - 1)]
    while stack:
        first, last = stack.pop()
        (x1, y1), (x2, y2) = points[first], points[last]
        dx, dy = x2 - x1, y2 - y1
        norm = math.hypot(dx, dy)
        best, index = 0.0, first
        for i in range(first + 1, last):
            x, y = points[i]
            d = abs(dy * (x - x1) - dx * (y - y1)) / norm if norm else math.hypot(x - x1, y - y1)
            if d > best:
                best, index = d, i
        if best > tolerance:
            keep[index] = True
            stack += [(first, index), (index, last)]
    return [pt for pt, k in zip(points, keep, strict=True) if k]


def build(geojson: dict, seeds: Path, tolerance: float = TOLERANCE) -> dict:
    """Project and simplify the 37 states. ``tolerance`` (SVG units) is the Douglas-Peucker
    tolerance; the state pages inline a coarser map to keep each page small."""
    keys, codes = state_lookup(seeds)
    features: dict[str, list[list[Ring]]] = {}
    errors: list[str] = []
    for feature in geojson["features"]:
        props = feature["properties"]
        state = keys.get(normalise_state_key(props["shapeName"]))
        if state is None:
            errors.append(f"no state matches geoBoundaries name {props['shapeName']!r}")
            continue
        if props.get("shapeISO") and props["shapeISO"] != codes[state]:
            found = props["shapeISO"]
            errors.append(f"{state}: code {codes[state]} but geoBoundaries says {found}")
        if codes[state] in features:
            errors.append(f"{state} appears twice")
        features[codes[state]] = polygons(feature["geometry"])
    missing = sorted(set(codes) - {s for s, c in codes.items() if c in features})
    errors += [f"{state} is missing from the boundaries" for state in missing]
    if errors:
        raise ValueError("; ".join(errors))

    kx = math.cos(math.radians(LAT0))
    points = [(lon, lat) for polys in features.values() for p in polys for r in p for lon, lat in r]
    min_x = min(lon for lon, _ in points) * kx
    max_x = max(lon for lon, _ in points) * kx
    min_lat = min(lat for _, lat in points)
    max_lat = max(lat for _, lat in points)
    scale = WIDTH / (max_x - min_x)
    height = math.ceil((max_lat - min_lat) * scale)

    def project(lon: float, lat: float) -> tuple[float, float]:
        return (lon * kx - min_x) * scale + PAD, (max_lat - lat) * scale + PAD

    def ring_path(ring: Ring) -> str:
        out: list[tuple[float, float]] = []
        for x, y in simplify([project(lon, lat) for lon, lat in ring], tolerance):
            pt = (round(x, 1), round(y, 1))
            if not out or pt != out[-1]:
                out.append(pt)
        if len(out) < 3:
            return ""
        coords = " ".join(f"{x:g},{y:g}" for x, y in out)
        return f"M{coords}Z"

    paths = {
        code: "".join(ring_path(ring) for poly in polys for ring in poly)
        for code, polys in sorted(features.items())
    }

    # Small states (Lagos, the FCT, Anambra...) are hard to spot at card size, so each gets a
    # ring centred on its bounding box: [cx, cy, r] in SVG units.
    rings: dict[str, list[float]] = {}
    for code, polys in sorted(features.items()):
        xs, ys = zip(*(project(lon, lat) for p in polys for r in p for lon, lat in r), strict=True)
        box_w, box_h = max(xs) - min(xs), max(ys) - min(ys)
        if box_w * box_h < SMALL_STATE:
            radius = min(max(max(box_w, box_h) / 2 + 8, 16), RING_MAX)
            centre = ((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2)
            rings[code] = [round(centre[0], 1), round(centre[1], 1), round(radius, 1)]
    return {
        "viewBox": f"0 0 {WIDTH + 2 * PAD} {height + 2 * PAD}",
        "attribution": ATTRIBUTION,
        "paths": paths,
        "rings": rings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the locator map's SVG paths.")
    parser.add_argument("--geojson", type=Path, default=DEFAULT_GEOJSON)
    parser.add_argument("--seeds", type=Path, default=SEEDS)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    try:
        doc = build(json.loads(args.geojson.read_text(encoding="utf-8")), args.seeds)
    except ValueError as error:
        print(f"Map build failed: {error}", file=sys.stderr)
        return 1
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(doc, separators=(",", ":")) + "\n", encoding="utf-8")
    print(f"wrote {args.out} ({len(doc['paths'])} states, {args.out.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
