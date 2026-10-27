"""The disclosure gate: the only code that writes to ``data/public/aggregates/``.

Every survey aggregate passes through :func:`publish` on its way out of the restricted zone:

1. **Disclosure check.** A cell (one estimate) with fewer than 30 unweighted respondents
   in its denominator has its estimate, SE, interval, effective n and df set to null and
   ``suppressed = true``. The number of suppressed cells goes in the manifest. The rule
   protects privacy; it says nothing about reliability.
2. **Precision flag.** Every row gets ``precision_flag`` (NCHS standard plus the project's
   fewer-than-10-events rule, see :mod:`curbcut_ingest.precision`): reliable / review /
   unreliable, or "suppressed" when the disclosure check removed the estimate.
   ``precision_reason`` says why.
3. **Columns that leave.** Only :data:`PUBLIC_COLUMNS`. The unweighted numerator count
   (``n_events``) is used for the flag and then dropped.
4. **Manifest.** ``manifest.json`` in the output root gets one entry per file: source,
   dataset version, terms, SHA-256, script commit, threshold, suppression count, design.

Files for a source that is *held* (MPI 2021 until NBS replies, ``docs/STATUS.md``) are
written to a git-ignored sub-folder with their own manifest; the committed manifest only
records that they are held.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import subprocess
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

import pandas as pd

from curbcut_ingest import precision

ROOT = Path(__file__).resolve().parents[4]
AGGREGATES = ROOT / "data" / "public" / "aggregates"
THRESHOLD = 30
SUPPRESSED = "suppressed"

# Columns the R step must provide (``packages/ingest/R/estimate.R``). ``breakdown`` names an
# extra dimension (sector, wealth_quintile, age_band) and ``breakdown_level`` its level;
# both are "all" on rows without one. One cell = source, measure, geography_level,
# geography, age_group, sex, breakdown, breakdown_level.
RAW_COLUMNS = (
    "measure",
    "geography_level",
    "geography",
    "age_group",
    "sex",
    "breakdown",
    "breakdown_level",
    "estimate",
    "se",
    "ci_low",
    "ci_high",
    "n_unweighted",
    "n_events",
    "n_effective",
    "df",
)
PUBLIC_COLUMNS = (
    "source",
    "dataset_version",
    "measure",
    "geography_level",
    "geography",
    "age_group",
    "sex",
    "breakdown",
    "breakdown_level",
    "estimate",
    "se",
    "ci_low",
    "ci_high",
    "n_unweighted",
    "n_effective",
    "df",
    "precision_flag",
    "precision_reason",
    "suppressed",
)
NULLED = ("estimate", "se", "ci_low", "ci_high", "n_effective", "df")
DECIMALS = {"estimate": 6, "se": 6, "ci_low": 6, "ci_high": 6, "n_effective": 1, "df": 0}


class GateError(ValueError):
    """The input does not have the shape the gate expects; nothing is written."""


@dataclass(frozen=True)
class Dataset:
    source: str
    version: str
    title: str
    citation: str
    terms: str
    design: str
    held: bool = False
    held_reason: str = ""
    extra: Mapping[str, Any] = field(default_factory=dict)


def gate(raw: pd.DataFrame, dataset: Dataset, threshold: int = THRESHOLD) -> pd.DataFrame:
    """Apply the disclosure check and precision flag. Returns public rows only."""
    missing = [c for c in RAW_COLUMNS if c not in raw.columns]
    if missing:
        raise GateError(f"raw estimates lack columns {missing}")
    out = raw.loc[:, list(RAW_COLUMNS)].copy()
    n = pd.to_numeric(out["n_unweighted"], errors="raise")
    if n.isna().any() or (n < 0).any():
        raise GateError("n_unweighted must be present and non-negative on every row")
    out["n_unweighted"] = n.astype("int64")
    small = out["n_unweighted"] < threshold

    flags, reasons = [], []
    records = cast(list[dict[str, Any]], out.to_dict("records"))
    for row in records:
        if row["n_unweighted"] < threshold:
            flags.append(SUPPRESSED)
            reasons.append(f"n<{threshold} (disclosure)")
            continue
        events = int(row["n_events"])
        result = precision.nchs_flag(
            estimate=_num(row["estimate"]),
            ci_low=_num(row["ci_low"]),
            ci_high=_num(row["ci_high"]),
            n=int(row["n_unweighted"]),
            n_effective=_num(row["n_effective"]),
            events=events,
            df=None if pd.isna(row["df"]) else float(row["df"]),
        )
        result = precision.low_events(result, events)
        flags.append(result.flag)
        reasons.append(result.reason)
    out["precision_flag"] = flags
    out["precision_reason"] = reasons
    for column in NULLED:
        out[column] = pd.to_numeric(out[column], errors="coerce").astype("float64")
        out.loc[small, column] = math.nan
        out[column] = out[column].round(DECIMALS[column])
    out["df"] = out["df"].astype("Int64")
    out["suppressed"] = small
    out["source"] = dataset.source
    out["dataset_version"] = dataset.version
    return out.loc[:, list(PUBLIC_COLUMNS)].reset_index(drop=True)


def _num(value: Any) -> float:
    return math.nan if pd.isna(value) else float(value)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def script_commit(root: Path = ROOT) -> str:
    """HEAD commit, with "-dirty" if tracked files under packages/ingest have changed."""
    try:
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, check=True
        ).stdout.strip()
        status = subprocess.run(
            ["git", "status", "--porcelain", "--", "packages/ingest"],
            cwd=root,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"
    return f"{head}-dirty" if status else head


def write_csv(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = frame.to_csv(index=False, lineterminator="\n", na_rep="")
    path.write_text(text, encoding="utf-8", newline="\n")


def _load_manifest(path: Path) -> dict[str, Any]:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def _save_manifest(path: Path, manifest: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    path.write_text(text, encoding="utf-8", newline="\n")


MANIFEST_HEADER = {
    "description": (
        "Survey aggregates that passed the Curb Cut disclosure gate "
        "(packages/ingest/src/curbcut_ingest/disclosure.py)."
    ),
    "disclosure_rule": (
        "Cells with fewer than 30 unweighted respondents in the denominator are suppressed: "
        "estimate, se, interval, n_effective and df are null and suppressed = true."
    ),
    "precision_standard": (
        "NCHS Data Presentation Standards for Proportions (Parker et al. 2017, Vital Health "
        "Stat 2(175)); see docs/verification.md D42."
    ),
    "interval": "95% Korn-Graubard (Clopper-Pearson with effective n and design df).",
    "reproduce": "docs/reproduce.md",
}


def publish(
    raw: pd.DataFrame,
    dataset: Dataset,
    filename: str,
    out_root: Path = AGGREGATES,
    threshold: int = THRESHOLD,
) -> tuple[Path, dict[str, Any]]:
    """Gate ``raw`` and write it under ``out_root``; record it in the manifest(s)."""
    public = gate(raw, dataset, threshold)
    folder = out_root / dataset.source if dataset.held else out_root
    path = folder / filename
    write_csv(public, path)
    key = path.relative_to(out_root).as_posix()
    entry: dict[str, Any] = {
        "source": dataset.title,
        "dataset_version": dataset.version,
        "citation": dataset.citation,
        "terms": dataset.terms,
        "design": dataset.design,
        "sha256": sha256(path),
        "rows": len(public),
        "suppressed_cells": int(public["suppressed"].sum()),
        "disclosure_threshold": threshold,
        "precision_flags": {
            flag: int((public["precision_flag"] == flag).sum())
            for flag in (*precision.FLAGS, SUPPRESSED)
        },
        "script_commit": script_commit(),
        "generated_on": dt.date.today().isoformat(),
        **dict(dataset.extra),
    }
    if dataset.held:
        # Full entry next to the held file (git-ignored); the committed manifest only says
        # that the file exists and is held, so CI never needs it.
        held_manifest = folder / "manifest.json"
        local = {**_load_manifest(held_manifest), **MANIFEST_HEADER}
        local.setdefault("files", {})[key] = entry
        _save_manifest(held_manifest, local)
    manifest_path = out_root / "manifest.json"
    manifest = {**_load_manifest(manifest_path), **MANIFEST_HEADER}
    if dataset.held:
        manifest.setdefault("held", {})[key] = {
            "status": "held (not published)",
            "reason": dataset.held_reason,
            "source": dataset.title,
            "dataset_version": dataset.version,
        }
        manifest.setdefault("files", {}).pop(key, None)
    else:
        manifest.setdefault("files", {})[key] = entry
    _save_manifest(manifest_path, manifest)
    return path, entry
