"""Spatial analysis of the DHS 2024 direct state estimates (P4a step 3).

Runs ``packages/ingest/R/spatial.R`` on public inputs only: the disclosure-gated DHS 2024
aggregates in ``data/public/aggregates/``, the geoBoundaries polygons and the GRID3 facility
counts in ``data/public/spatial/facilities_state.csv`` (built by ``curbcut_ingest.grid3``).
Fay-Herriot failed its diagnostics (``docs/verification.md`` D56), so the direct estimates are
used throughout. No spatial method is ever run on JONAPWD (D17).

Writes ``data/public/spatial/``: ``neighbours.csv`` (queen contiguity, row-standardised weights),
``moran_global.csv``, ``lisa_disability3_18plus.csv`` (exploratory), ``profile_clusters.csv``
and ``profile_silhouette.csv`` (descriptive), ``services_vs_need.json`` (ecological) and
``summary.json`` (headline numbers and one plain-English sentence per result).

Run (local; needs R with ``spdep`` and ``sf``): ``uv run python -I -m curbcut_ingest.spatial``.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
from collections.abc import Sequence
from pathlib import Path

from curbcut_ingest.aggregate import rscript

ROOT = Path(__file__).resolve().parents[4]
R_SCRIPT = ROOT / "packages" / "ingest" / "R" / "spatial.R"
OUTCOME = ROOT / "data" / "public" / "aggregates" / "dhs2024_state.csv"
GEOJSON = ROOT / "data" / "public" / "geoboundaries" / "geoBoundaries-NGA-ADM1_simplified.geojson"
OUT = ROOT / "data" / "public" / "spatial"
FACILITIES = OUT / "facilities_state.csv"

DOMAINS = (
    "seeing_3plus",
    "hearing_3plus",
    "walking_3plus",
    "cognition_3plus",
    "selfcare_3plus",
    "communication_3plus",
)
"""The six WG-SS domains at the cut-off ("a lot of difficulty" or "cannot do at all")."""

DOMAIN_LABELS = {
    "seeing_3plus": "Difficulty seeing",
    "hearing_3plus": "Difficulty hearing",
    "walking_3plus": "Difficulty walking or climbing steps",
    "cognition_3plus": "Difficulty remembering or concentrating",
    "selfcare_3plus": "Difficulty with self-care",
    "communication_3plus": "Difficulty communicating",
}

KNOWN_PAIRS = (("NG-LA", "NG-OG"), ("NG-KN", "NG-JI"), ("NG-FC", "NG-NI"), ("NG-BO", "NG-YO"))
"""Lagos-Ogun, Kano-Jigawa, FCT-Niger, Borno-Yobe: must be neighbours after simplification."""

NSIM = 9999
SEED = 20261028
FDR_Q = 0.05
K_RANGE = (2, 6)


def moran_measures() -> list[dict[str, str]]:
    """The 8 global tests: disability3 and each domain for 18+, then disability3 for 5-17."""
    rows = [
        {
            "measure": "disability3",
            "age_group": "18+",
            "role": "primary",
            "label": "Disability among adults 18+",
        }
    ]
    rows += [
        {
            "measure": m,
            "age_group": "18+",
            "role": "domain",
            "label": f"{DOMAIN_LABELS[m]} among adults 18+",
        }
        for m in DOMAINS
    ]
    rows.append(
        {
            "measure": "disability3",
            "age_group": "5-17",
            "role": "secondary",
            "label": "Disability among children 5-17 (secondary analysis)",
        }
    )
    return rows


def spec(out_dir: Path, facilities: Path = FACILITIES) -> dict[str, object]:
    return {
        "outcome_csv": OUTCOME.as_posix(),
        "boundaries": GEOJSON.as_posix(),
        "boundary_key": "shapeISO",
        "snap": None,
        "known_pairs": [list(p) for p in KNOWN_PAIRS],
        "moran_measures": moran_measures(),
        "lisa": {"measure": "disability3", "age_group": "18+", "q": FDR_Q},
        "domains": list(DOMAINS),
        "cluster_age_group": "18+",
        "k_range": list(K_RANGE),
        "services": {"measure": "disability3", "age_group": "18+"},
        "facilities_csv": facilities.as_posix(),
        "nsim": NSIM,
        "seed": SEED,
        "out_dir": out_dir.as_posix(),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the spatial analysis on the direct estimates."
    )
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args(argv)
    with tempfile.TemporaryDirectory() as tmp:
        spec_path = Path(tmp) / "spatial_spec.json"
        spec_path.write_text(json.dumps(spec(args.out), indent=2), encoding="utf-8")
        subprocess.run([rscript(), str(R_SCRIPT), str(spec_path)], cwd=ROOT, check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
