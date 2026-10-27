"""Turn harmonised person-level files into public aggregates (restricted zone -> gate).

Steps for each source, all local (CI never runs this; it has no restricted data):

1. read ``data/restricted/derived/<source>.parquet`` (written by ``curbcut_ingest.restricted``);
2. add the 0/1 indicator for every measure and write an analysis file plus a JSON spec,
   both still under ``data/restricted/derived/``;
3. run ``packages/ingest/R/estimate.R`` (R ``survey``) on them, which writes raw cell
   estimates (every cell, including small ones) under ``data/restricted/derived/``;
4. pass the raw cells through :func:`curbcut_ingest.disclosure.publish`, the only writer to
   ``data/public/aggregates/``.

Run: ``uv run python -I -m curbcut_ingest.aggregate [--sources dhs2024 ghs_w4 ghs_w5 mpi2021]``.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from curbcut_ingest import disclosure
from curbcut_ingest.restricted import common as c

R_SCRIPT = c.ROOT / "packages" / "ingest" / "R" / "estimate.R"
WORK = c.DERIVED / "estimates"
AGES = ("18+", "5-17")
MPI_SCREENED = ("seeing", "hearing", "walking")
MPI_SCALED = ("selfcare", "cognition", "communication", "upper_body")


def _at_least_3(values: pd.Series) -> pd.Series:
    return (values >= 3).astype("Int8").where(values.notna())


def _equals(values: pd.Series, level: int) -> pd.Series:
    return (values == level).astype("Int8").where(values.notna())


def wg_indicators(frame: pd.DataFrame, levels: bool = False) -> dict[str, pd.Series]:
    """DISABILITY3 and, per WG domain, "a lot of difficulty or cannot do at all"."""
    out = {"disability3": frame["disability3"].astype("Int8")}
    for domain in c.WG_DOMAINS:
        out[f"{domain}_3plus"] = _at_least_3(frame[domain])
        if levels:
            for level in c.WG_LEVELS:
                out[f"{domain}_level_{level}"] = _equals(frame[domain], level)
    return out


def mpi_indicators(frame: pd.DataFrame) -> dict[str, pd.Series]:
    """MPI's own measures (never called DISABILITY3; see restricted.mpi2021)."""
    out: dict[str, pd.Series] = {}
    for domain in MPI_SCREENED:
        out[f"mpi_screener_{domain}_any"] = frame[f"mpi_{domain}_screener"].astype("Int8")
    for domain in MPI_SCALED:
        out[f"mpi_{domain}_3plus"] = _at_least_3(frame[f"mpi_{domain}"])
    return out


@dataclass(frozen=True)
class Group:
    """One family of cells: a filter, the variables to cross, and the measures."""

    by: list[str]  # analysis-frame columns crossed to form the cells
    targets: list[str]  # output column taking each by-column's levels, in the same order
    labels: dict[str, str]
    outcomes: list[str]
    filter: dict[str, str]

    def as_spec(self) -> dict[str, Any]:
        return {
            "by": self.by,
            "targets": self.targets,
            "labels": self.labels,
            "outcomes": self.outcomes,
            "filter": self.filter,
        }


BREAKDOWN_COLUMNS = {
    "sector": "sector",
    "wealth_quintile": "wealth_quintile",
    "age_band": "prevalence_age_band",
}
"""Breakdown name (published in ``breakdown``) -> analysis-frame column of its levels."""


def _group(
    level: str,
    by: str,
    age: str,
    outcomes: list[str],
    *,
    by_sex: bool = False,
    breakdown: str | None = None,
) -> Group:
    """Cells of ``by`` (national, zone or state_code) for one age group, optionally crossed
    with sex (into the ``sex`` column) and one breakdown (into ``breakdown_level``)."""
    labels = {
        "geography_level": level,
        "geography": "NG",
        "age_group": age,
        "sex": "all",
        "breakdown": "all",
        "breakdown_level": "all",
    }
    columns, targets = [by], ["geography"]
    if by_sex:
        columns.append("sex")
        targets.append("sex")
    if breakdown is not None:
        labels["breakdown"] = breakdown
        columns.append(BREAKDOWN_COLUMNS[breakdown])
        targets.append("breakdown_level")
    return Group(by=columns, targets=targets, labels=labels, outcomes=outcomes,
                 filter={"age_group": age})  # fmt: skip


GEOGRAPHIES = {"national": "national", "zone": "zone", "state": "state_code"}


def dhs_jobs(frame: pd.DataFrame) -> list[Job]:
    main = list(wg_indicators(frame))
    with_levels = list(wg_indicators(frame, levels=True))
    groups: dict[str, list[Group]] = {level: [] for level in GEOGRAPHIES}
    # Unchanged since P3: state x age, national x age with levels, national x sex.
    groups["state"] += [_group("state", "state_code", age, main) for age in AGES]
    groups["national"] += [_group("national", "national", age, with_levels) for age in AGES]
    groups["national"] += [_group("national", "national", age, main, by_sex=True) for age in AGES]
    # P4a step 1: state and zone by sex, zone overall.
    groups["state"] += [_group("state", "state_code", age, main, by_sex=True) for age in AGES]
    groups["zone"] += [_group("zone", "zone", age, main) for age in AGES]
    groups["zone"] += [_group("zone", "zone", age, main, by_sex=True) for age in AGES]
    # Urban/rural and wealth quintile at every level; age bands (DISABILITY3) above state.
    for level, column in GEOGRAPHIES.items():
        for breakdown in ("sector", "wealth_quintile"):
            groups[level] += [_group(level, column, age, main, breakdown=breakdown) for age in AGES]
        if level != "state":
            groups[level] += [
                _group(level, column, age, ["disability3"], breakdown="age_band") for age in AGES
            ]
    return [
        Job("dhs2024_state.csv", groups["state"], wg_indicators),
        Job("dhs2024_national.csv", groups["national"], lambda f: wg_indicators(f, levels=True)),
        Job("dhs2024_zone.csv", groups["zone"], wg_indicators),
    ]


def ghs_jobs(source: str) -> Callable[[pd.DataFrame], list[Job]]:
    def jobs(frame: pd.DataFrame) -> list[Job]:
        main = list(wg_indicators(frame))
        groups = [
            _group("national", "national", "18+", main),
            _group("zone", "zone", "18+", ["disability3"]),
        ]
        return [Job(f"{source}_national_zone.csv", groups, wg_indicators)]

    return jobs


def mpi_jobs(frame: pd.DataFrame) -> list[Job]:
    measures = list(mpi_indicators(frame))
    groups = [_group("state", "state_code", age, measures) for age in AGES]
    groups += [_group("national", "national", age, measures) for age in AGES]
    return [Job("mpi2021_state_national.csv", groups, mpi_indicators)]


@dataclass(frozen=True)
class Job:
    filename: str
    groups: list[Group]
    indicators: Callable[[pd.DataFrame], dict[str, pd.Series]]


DATASETS = {
    "dhs2024": disclosure.Dataset(
        source="dhs2024",
        version="NG2024DHS, recode 8B (NGPR8BFL)",
        title="Nigeria Demographic and Health Survey 2024",
        citation=(
            "National Population Commission (NPC) [Nigeria] and ICF. Nigeria Demographic and "
            "Health Survey 2024. Abuja, Nigeria, and Rockville, Maryland, USA: NPC and ICF."
        ),
        terms=(
            "DHS Program terms: registered project only ('Curb Cut: disability prevalence "
            "and poverty in Nigeria'); aggregates only, no microdata; a PDF of every "
            "publication goes to references@dhsprogram.com."
        ),
        design=(
            "De facto household members aged 5+ asked the WG-SS (hdis2-hdis8; 8 = don't "
            "know -> missing). Weight hv005/1e6, strata hv023, PSU hv021."
        ),
    ),
    "ghs_w4": disclosure.Dataset(
        source="ghs_w4",
        version="NGA_2018_GHSP-W4_v03_M",
        title="Nigeria General Household Survey-Panel 2018-2019, Wave 4",
        citation=(
            "National Bureau of Statistics (NBS), Nigeria. General Household Survey, Panel "
            "2018-2019, Wave 4 (NGA_2018_GHSP-W4_v03_M). World Bank Microdata Library."
        ),
        terms="World Bank Microdata Library public-use terms: aggregates only, cite the dataset.",
        design=(
            "Post-harvest sect4a, WG-SS s4aq23-s4aq33 (-1 too young -> missing), members 5+. "
            "Weight wt_wave4 (cross-section), strata 'strata', PSU 'cluster'. National and "
            "zone only (not representative by state)."
        ),
    ),
    "ghs_w5": disclosure.Dataset(
        source="ghs_w5",
        version="NGA_2023_GHSP-W5_v02_M",
        title="Nigeria General Household Survey-Panel 2023-2024, Wave 5",
        citation=(
            "National Bureau of Statistics (NBS), Nigeria. General Household Survey, Panel "
            "2023-2024, Wave 5 (NGA_2023_GHSP-W5_v02_M). World Bank Microdata Library."
        ),
        terms="World Bank Microdata Library public-use terms: aggregates only, cite the dataset.",
        design=(
            "Post-planting sect3, WG-SS s3q23-s3q28, members 5+. Weight wt_cross_wave5 "
            "(cross-section), strata 'strata', PSU 'cluster'. National and zone only."
        ),
    ),
    "mpi2021": disclosure.Dataset(
        source="mpi2021",
        version="NGA-NBS-MPI-2021-v1.0",
        title="NBS Multidimensional Poverty Index Survey 2021",
        citation="National Bureau of Statistics, Multidimentional Poverty index Survey 2021 v1.0",
        terms=(
            "NBS access terms: aggregated reporting only; an electronic copy of every "
            "publication goes to the National Data Archive."
        ),
        design=(
            "NOT the WG-SS (verification.md D39, D43): seeing/hearing/walking are yes/no "
            "screeners (mpi_screener_*_any); 1-4 items for self-care d11a, cognition d12a, "
            "communication = worse of d9a/d10a, upper body = worse of d13a/d14a (*_3plus). "
            "Weight pop_wgt/hhsize; strata a1 x a1b x a3 and PSU a4 are assumptions (D40)."
        ),
        # Released 2026-10-24 by the author (NBS access terms allow aggregated reporting).
    ),
}

JOBS: dict[str, Callable[[pd.DataFrame], list[Job]]] = {
    "dhs2024": dhs_jobs,
    "ghs_w4": ghs_jobs("ghs_w4"),
    "ghs_w5": ghs_jobs("ghs_w5"),
    "mpi2021": mpi_jobs,
}


DESIGN_COLUMNS = ["weight", "stratum", "psu", "state_code", "zone", "sex", "age_group", "sector"]


def analysis_frame(frame: pd.DataFrame, indicators: dict[str, pd.Series]) -> pd.DataFrame:
    """Design and breakdown columns plus the indicators (no identifiers, no raw answers).
    ``wealth_quintile`` is carried when the source has it (DHS only)."""
    columns = [*DESIGN_COLUMNS, *(["wealth_quintile"] if "wealth_quintile" in frame else [])]
    out = frame[columns].assign(national="NG")
    out["prevalence_age_band"] = c.prevalence_age_band(frame["age"])
    for name, values in indicators.items():
        out[name] = values.astype("float64")  # nanoparquet reads nullable ints poorly
    return out.reset_index(drop=True)


def rscript() -> str:
    found = os.environ.get("RSCRIPT") or shutil.which("Rscript")
    if found:
        return found
    default = Path("C:/Program Files/R/R-4.5.2/bin/Rscript.exe")
    if default.exists():
        return str(default)
    raise FileNotFoundError("Rscript not found; set RSCRIPT")


def run_job(source: str, frame: pd.DataFrame, job: Job, work: Path = WORK) -> pd.DataFrame:
    stem = job.filename.removesuffix(".csv")
    work.mkdir(parents=True, exist_ok=True)
    data_path = work / f"{stem}.input.parquet"
    out_path = work / f"{stem}.raw.csv"
    spec_path = work / f"{stem}.spec.json"
    analysis_frame(frame, job.indicators(frame)).to_parquet(data_path, index=False)
    spec = {
        "source": source,
        "input": data_path.as_posix(),
        "output": out_path.as_posix(),
        "groups": [g.as_spec() for g in job.groups],
    }
    spec_path.write_text(json.dumps(spec, indent=2) + "\n", encoding="utf-8", newline="\n")
    c.log(f"  R: {job.filename} ({len(job.groups)} groups)")
    run_r([rscript(), str(R_SCRIPT), str(spec_path)])
    return pd.read_csv(out_path, keep_default_na=True)


R_LOG_PREFIX = "estimate.R: "
"""estimate.R prints only counts, on lines starting with this; nothing else is shown."""


def run_r(cmd: list[str]) -> None:
    """Run R with its output captured. Only estimate.R's own count lines are printed; R's
    messages, warnings and errors (which could quote data) are withheld and only counted,
    the same rule as :func:`common.safe_main`."""
    result = subprocess.run(cmd, cwd=c.ROOT, capture_output=True, text=True, check=False)
    lines = [*(result.stdout or "").splitlines(), *(result.stderr or "").splitlines()]
    shown = [line for line in lines if line.startswith(R_LOG_PREFIX)]
    for line in shown:
        c.log(f"  {line}")
    withheld = sum(1 for line in lines if line.strip() and not line.startswith(R_LOG_PREFIX))
    if withheld:
        c.log(f"  R: {withheld} other output lines withheld (messages and warnings)")
    if result.returncode != 0:
        # No output attached, so a traceback cannot echo R's message.
        raise subprocess.CalledProcessError(result.returncode, cmd[:2])


@c.safe_main
def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Estimate, gate and publish aggregates.")
    parser.add_argument("--sources", nargs="+", choices=sorted(JOBS), default=sorted(JOBS))
    parser.add_argument("--derived", type=Path, default=c.DERIVED)
    parser.add_argument("--out-root", type=Path, default=disclosure.AGGREGATES)
    args = parser.parse_args(argv)
    for source in args.sources:
        c.log(f"{source}: reading harmonised file")
        frame = pd.read_parquet(args.derived / f"{source}.parquet")
        for job in JOBS[source](frame):
            raw = run_job(source, frame, job, args.derived / "estimates")
            path, entry = disclosure.publish(raw, DATASETS[source], job.filename, args.out_root)
            where = "held, git-ignored" if DATASETS[source].held else "public"
            c.log(
                f"  gate: {path.name} ({where}): {entry['rows']} cells, "
                f"{entry['suppressed_cells']} suppressed, flags {entry['precision_flags']}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
