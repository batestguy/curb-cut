"""Load, check and hold the public files the API serves.

The API reads the same public, disclosure-checked files the static site serves, so it
can never show anything the site does not. By default it downloads them from the live
Pages site (``CURBCUT_DATA_BASE``); ``CURBCUT_DATA_DIR`` reads a local directory instead
(development and tests, e.g. ``site/public/data``). Everything is held in memory as plain
Python rows: the files are small (about 150 KB in all).

If loading fails, the app still runs and reports itself not ready; the next attempt waits
for a backoff (30 s, doubling to 10 minutes), so a failing source is not hit on every
request.
"""

from __future__ import annotations

import hashlib
import json
import re
import tempfile
import threading
import time
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb

DEFAULT_BASE = "https://batestguy.github.io/curb-cut/data/"
MAX_BYTES = 5 * 1024 * 1024  # each file is far smaller; refuse anything absurd
TIMEOUT_S = 30
BACKOFF_START_S = 30.0
BACKOFF_MAX_S = 600.0
N_STATES = 37

CELL_COLUMNS = (
    "measure",
    "age_group",
    "sex",
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
# File name -> required columns (Parquet) or keys (JSON). All are served by the site.
PARQUET_FILES: dict[str, tuple[str, ...]] = {
    "dhs2024_state_prevalence.parquet": (
        "state",
        "state_code",
        "zone",
        *CELL_COLUMNS,
        "has_data",
        "population_2023",
    ),
    "dhs2024_national_zone.parquet": ("geography_level", "geography", *CELL_COLUMNS),
    "prevalence_comparison.parquet": (
        "figure_id",
        "sort_order",
        "label",
        "kind",
        "value_percent",
        "ci_low_percent",
        "ci_high_percent",
        "population",
        "definition",
        "source",
        "source_url",
    ),
}
STATE_KEYS = (
    "state",
    "state_code",
    "zone",
    "capital",
    "population_2023",
    "jonapwd_total",
    "share_of_national",
    "rank_of_37",
    "dhs2024",
)
POVERTY_KEYS = ("note", "estimates", "summary")
JSON_FILES = ("states.json", "poverty.json")
FILES = (*PARQUET_FILES, *JSON_FILES)

Fetch = Callable[[str], bytes]


class DataError(ValueError):
    """A public file is missing, unreadable or not what the API expects."""


def slug(name: str) -> str:
    """The site's state slug (``stateHref`` in ``site/src/format.js``): lower case, each
    run of other characters replaced by one hyphen, no hyphen at either end."""
    return re.sub(r"[^a-z]+", "-", name.lower()).strip("-")


def url_fetcher(base: str) -> Fetch:
    """Download ``base + name`` over HTTPS, refusing anything over ``MAX_BYTES``."""
    if not base.endswith("/"):
        base += "/"

    def fetch(name: str) -> bytes:
        request = urllib.request.Request(base + name, headers={"User-Agent": "curbcut-api"})
        with urllib.request.urlopen(request, timeout=TIMEOUT_S) as response:
            body = response.read(MAX_BYTES + 1)
        if len(body) > MAX_BYTES:
            raise DataError(f"{name} is larger than {MAX_BYTES} bytes")
        return body

    return fetch


def dir_fetcher(directory: Path) -> Fetch:
    def fetch(name: str) -> bytes:
        return (directory / name).read_bytes()

    return fetch


@dataclass(frozen=True)
class FileInfo:
    rows: int
    sha256: str
    bytes: int


@dataclass(frozen=True)
class Dataset:
    """Everything the endpoints serve, checked once at load."""

    state_cells: list[dict[str, Any]]
    national_zone_cells: list[dict[str, Any]]
    comparison: list[dict[str, Any]]
    states: list[dict[str, Any]]
    poverty: dict[str, Any]
    files: dict[str, FileInfo]
    loaded_at: str
    # Lookup: slug or ISO code (with or without "NG-"), lower case -> state record.
    state_index: dict[str, dict[str, Any]] = field(repr=False)


def _parquet_rows(name: str, body: bytes, required: tuple[str, ...]) -> list[dict[str, Any]]:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / name
        path.write_bytes(body)
        try:
            with duckdb.connect() as con:
                cursor = con.execute("select * from read_parquet(?)", [path.as_posix()])
                columns = [d[0] for d in cursor.description]
                rows = [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]
        except duckdb.Error as exc:
            raise DataError(f"{name} is not readable Parquet: {exc}") from exc
    missing = [c for c in required if c not in columns]
    if missing:
        raise DataError(f"{name} lacks columns {missing}")
    if not rows:
        raise DataError(f"{name} has no rows")
    return rows


def _json(name: str, body: bytes) -> Any:
    try:
        return json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DataError(f"{name} is not valid JSON: {exc}") from exc


def _check_states(states: Any) -> list[dict[str, Any]]:
    if not isinstance(states, list) or len(states) != N_STATES:
        raise DataError(f"states.json must list {N_STATES} states")
    for state in states:
        if not isinstance(state, dict):
            raise DataError("states.json holds a non-object entry")
        missing = [k for k in STATE_KEYS if k not in state]
        if missing:
            raise DataError(f"states.json entry lacks keys {missing}")
    if len({s["state_code"] for s in states}) != N_STATES:
        raise DataError("states.json state codes are not unique")
    return states


def _check_poverty(poverty: Any) -> dict[str, Any]:
    if not isinstance(poverty, dict):
        raise DataError("poverty.json must be an object")
    missing = [k for k in POVERTY_KEYS if k not in poverty]
    if missing:
        raise DataError(f"poverty.json lacks keys {missing}")
    if not poverty["estimates"] or not isinstance(poverty["estimates"], dict):
        raise DataError("poverty.json has no estimates")
    return poverty


def _index(states: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for state in states:
        code = str(state["state_code"]).lower()
        for key in (slug(state["state"]), code, code.removeprefix("ng-")):
            index[key] = state
    if len(index) != 3 * N_STATES:
        raise DataError("state slugs and codes overlap")
    return index


def load(fetch: Fetch) -> Dataset:
    """Fetch every file, check it and build the in-memory dataset; raises on any fault."""
    bodies: dict[str, bytes] = {}
    for name in FILES:
        try:
            bodies[name] = fetch(name)
        except DataError:
            raise
        except Exception as exc:  # network, HTTP or file errors, reported as one kind
            raise DataError(f"could not fetch {name}: {exc}") from exc
    tables = {name: _parquet_rows(name, bodies[name], cols) for name, cols in PARQUET_FILES.items()}
    states = _check_states(_json("states.json", bodies["states.json"]))
    poverty = _check_poverty(_json("poverty.json", bodies["poverty.json"]))
    state_cells = tables["dhs2024_state_prevalence.parquet"]
    if len({r["state_code"] for r in state_cells}) != N_STATES:
        raise DataError(f"dhs2024_state_prevalence.parquet must cover {N_STATES} states")
    national_zone = tables["dhs2024_national_zone.parquet"]
    if not any(r["geography_level"] == "national" for r in national_zone):
        raise DataError("dhs2024_national_zone.parquet has no national cells")
    rows = {
        **{name: len(rows) for name, rows in tables.items()},
        "states.json": len(states),
        "poverty.json": len(poverty["estimates"]),
    }
    files = {
        name: FileInfo(rows=rows[name], sha256=hashlib.sha256(body).hexdigest(), bytes=len(body))
        for name, body in bodies.items()
    }
    return Dataset(
        state_cells=state_cells,
        national_zone_cells=national_zone,
        comparison=sorted(tables["prevalence_comparison.parquet"], key=lambda r: r["sort_order"]),
        states=states,
        poverty=poverty,
        files=files,
        loaded_at=datetime.now(UTC).isoformat(timespec="seconds"),
        state_index=_index(states),
    )


class Store:
    """Holds the dataset; loads lazily and retries with a backoff after a failure."""

    def __init__(self, fetch: Fetch, source: str, clock: Callable[[], float] = time.monotonic):
        self.fetch = fetch
        self.source = source
        self.clock = clock
        self.data: Dataset | None = None
        self.error: str | None = None
        self.attempts = 0
        self._next_try = 0.0
        self._backoff = BACKOFF_START_S
        self._lock = threading.Lock()

    def ensure(self) -> Dataset | None:
        """The dataset, loading it if it is missing and the backoff has passed."""
        if self.data is not None:
            return self.data
        with self._lock:
            if self.data is None and self.clock() >= self._next_try:
                self.attempts += 1
                try:
                    self.data = load(self.fetch)
                    self.error = None
                except DataError as exc:
                    self.error = str(exc)
                    self._next_try = self.clock() + self._backoff
                    self._backoff = min(self._backoff * 2, BACKOFF_MAX_S)
        return self.data

    def retry_in(self) -> float | None:
        """Seconds until the next load attempt, or None once loaded."""
        if self.data is not None:
            return None
        return max(0.0, self._next_try - self.clock())


def store_from_env(env: Mapping[str, str]) -> Store:
    directory = env.get("CURBCUT_DATA_DIR")
    if directory:
        path = Path(directory).resolve()
        return Store(dir_fetcher(path), f"directory {path}")
    base = env.get("CURBCUT_DATA_BASE") or DEFAULT_BASE
    return Store(url_fetcher(base), base)
