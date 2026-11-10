"""The disclosure gate: the only code that writes to ``data/public/aggregates/``.

Every survey aggregate passes through :func:`publish` on its way out of the restricted zone:

1. **Disclosure check.** A cell (one estimate) with fewer than 30 unweighted respondents
   in its denominator is suppressed (*primary* suppression). Because published cells add
   up (quintiles to their state, states to their zone and to Nigeria, women and men to
   both sexes, severity levels to 100%), one suppressed cell among published siblings
   could be recovered by subtraction; :func:`complementary` then also suppresses the
   smallest sibling (*secondary* suppression), repeating until no partition has exactly
   one suppressed cell. A suppressed cell has its estimate, SE, interval, unweighted and
   effective n and df set to null and ``suppressed = true``. The counts go in the
   manifest. The rule protects privacy; it says nothing about reliability.
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

**Model estimates** (P5: one adjusted difference per row, not a survey cell) leave through
:func:`publish_estimates`. The rule is on both arms of the comparison: an estimate whose
exposed (or onset) group or whose comparison group has fewer than 30 unweighted units is
suppressed (numbers and both counts set to null). Estimates are not parts of a published
total, so there is no complementary suppression. Scalar results that go with them (checks,
sensitivity values, counts) leave through :func:`publish_summary`, where any count under 30
is suppressed. Both record the same manifest entry as :func:`publish`.
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
KEY = (
    "measure",
    "geography_level",
    "geography",
    "age_group",
    "sex",
    "breakdown",
    "breakdown_level",
)
"""One cell. Within a source, no two cells share a key."""
SECONDARY_REASON = "complementary suppression (disclosure)"
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


def _checked(raw: pd.DataFrame) -> pd.DataFrame:
    missing = [c for c in RAW_COLUMNS if c not in raw.columns]
    if missing:
        raise GateError(f"raw estimates lack columns {missing}")
    out = raw.loc[:, list(RAW_COLUMNS)].copy()
    n = pd.to_numeric(out["n_unweighted"], errors="raise")
    if n.isna().any() or (n < 0).any():
        raise GateError("n_unweighted must be present and non-negative on every row")
    out["n_unweighted"] = n.astype("int64")
    if out.duplicated(list(KEY)).any():
        raise GateError("two raw cells share a key")
    return out


def _partitions(cells: pd.DataFrame, zone_of: Mapping[str, str]) -> list[list[int]]:
    """Groups of sibling cells whose estimates combine into a published (or known) total.

    - a breakdown's levels (quintiles, sectors, age bands) within one geography/sex/age;
    - women and men within one geography/breakdown level/age;
    - states within Nigeria and within their zone, and zones within Nigeria;
    - the four severity levels of one domain (``<domain>_level_1`` .. ``_4``), which sum
      to 100%.

    The parent need not be published: a partition is protected as if its total were known.
    """
    groups: list[list[int]] = []

    def add(frame: pd.DataFrame, by: list[str]) -> None:
        if frame.empty:
            return
        for _, part in frame.groupby(by, dropna=False, sort=True):
            groups.append(sorted(int(i) for i in part.index))

    add(cells[cells["breakdown"] != "all"], [k for k in KEY if k != "breakdown_level"])
    add(cells[cells["sex"] != "all"], [k for k in KEY if k != "sex"])
    no_geo = [k for k in KEY if k not in ("geography_level", "geography")]
    states = cells[cells["geography_level"] == "state"]
    add(states, no_geo)
    if zone_of and not states.empty:
        zones = states["geography"].map(zone_of)
        if zones.isna().any():
            raise GateError("a state code has no zone")
        add(states.assign(_zone=zones), [*no_geo, "_zone"])
    add(cells[cells["geography_level"] == "zone"], no_geo)
    domain = cells["measure"].str.extract(r"^(?P<domain>.+)_level_[1-4]$")["domain"]
    levels = cells[domain.notna()].assign(_domain=domain[domain.notna()])
    add(levels, ["_domain", *[k for k in KEY if k != "measure"]])
    return groups


def complementary(
    cells: pd.DataFrame,
    zone_of: Mapping[str, str] | None = None,
    threshold: int = THRESHOLD,
) -> pd.Series:
    """Primary plus secondary suppression over all of one source's cells (every file).

    Returns a boolean Series on ``cells.index``. Run it on the cells of every file of a
    source together, since a state cell can be recovered from the national one.
    """
    frame = _checked(cells.reset_index(drop=True))
    n = frame["n_unweighted"].to_numpy()
    suppressed = n < threshold
    groups = _partitions(frame, zone_of or {})
    changed = True
    while changed:
        changed = False
        for group in groups:
            hidden = [i for i in group if suppressed[i]]
            if len(hidden) != 1:
                continue
            shown = [i for i in group if not suppressed[i]]
            if not shown:
                # No published sibling to subtract. (If the cell is its total's only part,
                # the total has the same n and is suppressed too.)
                continue
            pick = min(shown, key=lambda i: (n[i], tuple(str(frame.at[i, k]) for k in KEY)))
            suppressed[pick] = True
            changed = True
    return pd.Series(suppressed, index=cells.index)


def gate(
    raw: pd.DataFrame,
    dataset: Dataset,
    threshold: int = THRESHOLD,
    suppress: pd.Series | None = None,
) -> pd.DataFrame:
    """Apply the disclosure check and precision flag. Returns public rows only.

    ``suppress`` (aligned to ``raw.index``) comes from :func:`complementary` run over all of
    the source's files; without it, complementary suppression runs on ``raw`` alone.
    """
    out = _checked(raw)
    if suppress is None:
        suppress = complementary(raw, threshold=threshold)
    hide = pd.Series(suppress.to_numpy(dtype=bool), index=out.index)
    if ((out["n_unweighted"] < threshold) & ~hide).any():
        raise GateError("a cell under the threshold is not marked for suppression")

    flags, reasons = [], []
    records = cast(list[dict[str, Any]], out.to_dict("records"))
    for row, hidden in zip(records, hide, strict=True):
        if hidden:
            flags.append(SUPPRESSED)
            primary = row["n_unweighted"] < threshold
            reasons.append(f"n<{threshold} (disclosure)" if primary else SECONDARY_REASON)
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
        out.loc[hide, column] = math.nan
        out[column] = out[column].round(DECIMALS[column])
    out["df"] = out["df"].astype("Int64")
    out["n_unweighted"] = out["n_unweighted"].astype("Int64").mask(hide)
    out["suppressed"] = hide
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
        "Cells with fewer than 30 unweighted respondents in the denominator are suppressed "
        "(primary). Where a partition of cells that add up (breakdown levels, women and men, "
        "states within a zone or Nigeria, zones, severity levels) would then hold exactly one "
        "suppressed cell, its smallest other cell is suppressed too (secondary), until none "
        "does. Suppressed cells have estimate, se, interval, n_unweighted, n_effective and df "
        "null and suppressed = true."
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
    suppress: pd.Series | None = None,
) -> tuple[Path, dict[str, Any]]:
    """Gate ``raw`` and write it under ``out_root``; record it in the manifest(s)."""
    public = gate(raw, dataset, threshold, suppress)
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
        "secondary_suppressed_cells": int((public["precision_reason"] == SECONDARY_REASON).sum()),
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


# --- Model estimates (P5) -------------------------------------------------------------------

ESTIMATE_COLUMNS = (
    "analysis",
    "group",
    "estimate_id",
    "label",
    "outcome",
    "exposure",
    "scale",
    "learners",
    "estimate",
    "se",
    "ci_low",
    "ci_high",
    "pval",
    "holm_p",
    "supported",
    "mu0",
    "n",
    "n_exposed",
    "n_unexposed",
)
"""Columns of one model estimate. ``n_exposed`` is the exposed (or onset) group's unweighted
count and ``n_unexposed`` the comparison group's; ``n`` is their sum."""
PUBLIC_ESTIMATE_COLUMNS = ("source", "dataset_version", *ESTIMATE_COLUMNS, "suppressed")
ESTIMATE_NULLED = ("estimate", "se", "ci_low", "ci_high", "pval", "holm_p", "supported", "mu0")
ESTIMATE_DECIMALS = {
    "estimate": 6,
    "se": 6,
    "ci_low": 6,
    "ci_high": 6,
    "mu0": 6,
    "pval": 10,
    "holm_p": 10,
}
SUMMARY_COLUMNS = ("analysis", "section", "item_id", "label", "kind", "value", "value_text")
"""One scalar result. ``kind`` is count, share (0-1), number, flag (1 or 0) or text."""
SUMMARY_KINDS = ("count", "share", "number", "flag", "text")
PUBLIC_SUMMARY_COLUMNS = ("source", "dataset_version", *SUMMARY_COLUMNS, "suppressed")
SUMMARY_DECIMALS = 8

ESTIMATE_RULE = (
    "Model estimates: suppressed (numbers and both group counts null, suppressed = true) if "
    "the exposed (or onset) group or the comparison group has fewer than 30 unweighted units. "
    "No complementary suppression: estimates are not parts of a published total."
)
SUMMARY_RULE = "Scalar results: a count under 30 (above 0) is suppressed (value null)."


def parse_count(value: Any) -> int | None:
    """A count from the analysis files, which write counts as safe text ("5,269", "<30").

    "<k" (a masked count from 1 to k-1) becomes k-1, so it is always below the threshold.
    Missing values stay None.
    """
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    if isinstance(value, bool):
        raise GateError("a count cannot be a boolean")
    if isinstance(value, int | float):
        return int(value)
    text = str(value).strip().replace(",", "")
    if text.startswith("<"):
        return int(text[1:]) - 1
    return int(text)


def gate_estimates(raw: pd.DataFrame, dataset: Dataset, threshold: int = THRESHOLD) -> pd.DataFrame:
    """Apply the estimate rule (module docstring). Returns public rows only."""
    missing = [c for c in ESTIMATE_COLUMNS if c not in raw.columns]
    if missing:
        raise GateError(f"model estimates lack columns {missing}")
    out = raw.loc[:, list(ESTIMATE_COLUMNS)].copy().reset_index(drop=True)
    if out["estimate_id"].duplicated().any():
        raise GateError("two model estimates share an estimate_id")
    for column in ("n", "n_exposed", "n_unexposed"):
        counts = [parse_count(v) for v in out[column]]
        if any(c is None or c < 0 for c in counts):
            raise GateError(f"{column} must be present and non-negative on every estimate")
        out[column] = pd.array(counts, dtype="Int64")
    hide = ((out["n_exposed"] < threshold) | (out["n_unexposed"] < threshold)).astype(bool)
    for column in ESTIMATE_NULLED:
        if column == "supported":
            out[column] = out[column].astype("boolean").mask(hide)
            continue
        out[column] = pd.to_numeric(out[column], errors="coerce").astype("float64")
        out.loc[hide, column] = math.nan
        out[column] = out[column].round(ESTIMATE_DECIMALS[column])
    for column in ("n_exposed", "n_unexposed"):
        out[column] = out[column].mask(hide)
    inside = (out["ci_low"] <= out["estimate"]) & (out["estimate"] <= out["ci_high"])
    if (~hide & ~inside).any():
        raise GateError("an estimate lies outside its own interval, or has no interval")
    out["suppressed"] = hide
    out["source"] = dataset.source
    out["dataset_version"] = dataset.version
    return out.loc[:, list(PUBLIC_ESTIMATE_COLUMNS)]


def gate_summary(raw: pd.DataFrame, dataset: Dataset, threshold: int = THRESHOLD) -> pd.DataFrame:
    """Apply the summary rule (module docstring). Returns public rows only."""
    missing = [c for c in SUMMARY_COLUMNS if c not in raw.columns]
    if missing:
        raise GateError(f"summary rows lack columns {missing}")
    out = raw.loc[:, list(SUMMARY_COLUMNS)].copy().reset_index(drop=True)
    if out.duplicated(["analysis", "item_id"]).any():
        raise GateError("two summary rows share an item_id")
    unknown = sorted(set(out["kind"]) - set(SUMMARY_KINDS))
    if unknown:
        raise GateError(f"unknown summary kinds {unknown}")
    values: list[float] = []
    hide: list[bool] = []
    for kind, value in zip(out["kind"], out["value"], strict=True):
        if kind == "text":
            values.append(math.nan)
            hide.append(False)
            continue
        if kind == "count":
            count = parse_count(value)
            if count is None:
                raise GateError("a count item has no value")
            small = 0 < count < threshold
            values.append(math.nan if small else float(count))
            hide.append(small)
            continue
        number = _num(value)
        if math.isnan(number):
            raise GateError("a numeric summary item has no value")
        values.append(round(number, SUMMARY_DECIMALS))
        hide.append(False)
    out["value"] = pd.Series(values, dtype="float64")
    texts = out["value_text"].astype("string")
    if ((out["kind"] == "text") & texts.isna()).any():
        raise GateError("a text item has no value_text")
    out["value_text"] = texts
    out["suppressed"] = hide
    out["source"] = dataset.source
    out["dataset_version"] = dataset.version
    return out.loc[:, list(PUBLIC_SUMMARY_COLUMNS)]


def _write_entry(
    public: pd.DataFrame,
    dataset: Dataset,
    filename: str,
    out_root: Path,
    threshold: int,
    rule: str,
) -> tuple[Path, dict[str, Any]]:
    if dataset.held:
        raise GateError("model estimates and summaries are never held")
    path = out_root / filename
    write_csv(public, path)
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
        "disclosure_rule": rule,
        "script_commit": script_commit(),
        "generated_on": dt.date.today().isoformat(),
        **dict(dataset.extra),
    }
    manifest_path = out_root / "manifest.json"
    manifest = {**_load_manifest(manifest_path), **MANIFEST_HEADER}
    manifest.setdefault("files", {})[path.relative_to(out_root).as_posix()] = entry
    _save_manifest(manifest_path, manifest)
    return path, entry


def publish_estimates(
    raw: pd.DataFrame,
    dataset: Dataset,
    filename: str,
    out_root: Path = AGGREGATES,
    threshold: int = THRESHOLD,
) -> tuple[Path, dict[str, Any]]:
    """Gate model estimates (:func:`gate_estimates`), write them and record the manifest."""
    public = gate_estimates(raw, dataset, threshold)
    return _write_entry(public, dataset, filename, out_root, threshold, ESTIMATE_RULE)


def publish_summary(
    raw: pd.DataFrame,
    dataset: Dataset,
    filename: str,
    out_root: Path = AGGREGATES,
    threshold: int = THRESHOLD,
) -> tuple[Path, dict[str, Any]]:
    """Gate scalar results (:func:`gate_summary`), write them and record the manifest."""
    public = gate_summary(raw, dataset, threshold)
    return _write_entry(public, dataset, filename, out_root, threshold, SUMMARY_RULE)


# --- Descriptive tables by group (P5 manuscript Table 1) -------------------------------------

TABLE_COLUMNS = ("table", "characteristic", "category", "kind", "group", "n", "value")
"""One cell of a descriptive table: the weighted ``value`` (a share 0-1, or a mean) of
``characteristic`` = ``category`` in ``group`` (e.g. exposed / unexposed), from ``n``
unweighted units. For a share, ``n`` is the units in the category; for a mean, the units in
the group. ``kind`` is "share" or "mean"."""
PUBLIC_TABLE_COLUMNS = ("source", "dataset_version", *TABLE_COLUMNS, "suppressed")
TABLE_RULE = (
    "Descriptive tables: a cell from fewer than 30 unweighted units (above 0) is suppressed "
    "(n and value null). Shares of one characteristic in one group add to 1, so where exactly "
    "one share would be suppressed the smallest other share is suppressed too, until none is "
    "alone."
)


def gate_table(raw: pd.DataFrame, dataset: Dataset, threshold: int = THRESHOLD) -> pd.DataFrame:
    """Apply the table rule (:data:`TABLE_RULE`). Returns public rows only."""
    missing = [c for c in TABLE_COLUMNS if c not in raw.columns]
    if missing:
        raise GateError(f"table rows lack columns {missing}")
    out = raw.loc[:, list(TABLE_COLUMNS)].copy().reset_index(drop=True)
    if out.duplicated(["table", "characteristic", "category", "group"]).any():
        raise GateError("two table cells share a key")
    if sorted(set(out["kind"]) - {"share", "mean"}):
        raise GateError("a table cell's kind must be share or mean")
    counts = [parse_count(v) for v in out["n"]]
    if any(c is None or c < 0 for c in counts):
        raise GateError("n must be present and non-negative on every table cell")
    n = pd.Series(counts, dtype="int64")
    hide = ((n > 0) & (n < threshold)).to_numpy().copy()
    shares = out["kind"] == "share"
    for _, idx in out[shares].groupby(["table", "characteristic", "group"]).groups.items():
        rows = list(idx)
        while sum(hide[r] for r in rows) == 1 and len(rows) > 1:
            shown = [r for r in rows if not hide[r]]
            hide[min(shown, key=lambda r: (n[r], r))] = True
    value = pd.to_numeric(out["value"], errors="coerce").astype("float64")
    if value[~hide].isna().any():
        raise GateError("a shown table cell has no value")
    out["value"] = value.mask(hide).round(SUMMARY_DECIMALS)
    out["n"] = pd.array(counts, dtype="Int64")
    out["n"] = out["n"].mask(pd.Series(hide))
    out["suppressed"] = hide
    out["source"] = dataset.source
    out["dataset_version"] = dataset.version
    return out.loc[:, list(PUBLIC_TABLE_COLUMNS)]


def publish_table(
    raw: pd.DataFrame,
    dataset: Dataset,
    filename: str,
    out_root: Path = AGGREGATES,
    threshold: int = THRESHOLD,
) -> tuple[Path, dict[str, Any]]:
    """Gate a descriptive table (:func:`gate_table`), write it and record the manifest."""
    public = gate_table(raw, dataset, threshold)
    return _write_entry(public, dataset, filename, out_root, threshold, TABLE_RULE)
