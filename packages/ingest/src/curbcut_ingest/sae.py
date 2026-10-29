"""Fay-Herriot small-area estimates of adult disability prevalence by state (P4a step 2).

Runs ``packages/ingest/R/fay_herriot.R`` on public inputs only: the disclosure-gated DHS 2024
aggregates in ``data/public/aggregates/``, the covariates in ``data/public/covariates/`` and the
geoBoundaries polygons. The covariates, the selection rule and the failure tests were fixed
before any fit, in ``docs/fay-herriot-covariates.md``; this module only writes the spec.

Writes ``data/public/sae/``: ``fh_state.csv`` (one row per state), ``fh_model_selection.csv``
(every candidate model with its ML BIC) and ``fh_summary.json`` (choice, diagnostics,
benchmark, bootstrap and spatial comparison).

Run (local; needs R with ``sae``, ``spdep`` and ``sf``): ``uv run python -I -m curbcut_ingest.sae``.
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
R_SCRIPT = ROOT / "packages" / "ingest" / "R" / "fay_herriot.R"
AGGREGATES = ROOT / "data" / "public" / "aggregates"
COVARIATES = ROOT / "data" / "public" / "covariates" / "state_covariates.csv"
GEOJSON = ROOT / "data" / "public" / "geoboundaries" / "geoBoundaries-NGA-ADM1_simplified.geojson"
OUT = ROOT / "data" / "public" / "sae"

COVARIATE_COLUMNS = (
    "c1_share_60plus",
    "c2_urban_share",
    "c3_mpi_headcount",
    "c4_female_literacy",
    "c5_log_density",
)
"""C1-C5 of docs/fay-herriot-covariates.md, frozen 2026-10-28."""
MAX_COVARIATES = 3
BIC_TIE = 2.0
BOOTSTRAP_B = 1000
SEED = 20261028


def spec(out_dir: Path, measure: str = "disability3", age_group: str = "18+") -> dict[str, object]:
    return {
        "measure": measure,
        "age_group": age_group,
        "outcome_csv": (AGGREGATES / "dhs2024_state.csv").as_posix(),
        "national_csv": (AGGREGATES / "dhs2024_national.csv").as_posix(),
        "covariates_csv": COVARIATES.as_posix(),
        "covariate_key": "state_code",
        "covariates": list(COVARIATE_COLUMNS),
        "max_covariates": MAX_COVARIATES,
        "bic_tie": BIC_TIE,
        "weight_column": "wp2020_pop_18plus",
        "bootstrap_b": BOOTSTRAP_B,
        "seed": SEED,
        "boundaries": GEOJSON.as_posix(),
        "boundary_key": "shapeISO",
        "out_dir": out_dir.as_posix(),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fit the arcsine Fay-Herriot model.")
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args(argv)
    with tempfile.TemporaryDirectory() as tmp:
        spec_path = Path(tmp) / "fh_spec.json"
        spec_path.write_text(json.dumps(spec(args.out), indent=2), encoding="utf-8")
        subprocess.run([rscript(), str(R_SCRIPT), str(spec_path)], cwd=ROOT, check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
