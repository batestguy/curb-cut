"""Load, check and hold the public files the API serves.

The API reads the same public, disclosure-checked files the static site serves, so it
can never show anything the site does not. By default it downloads them from the live
Pages site (``CURBCUT_DATA_BASE``); ``CURBCUT_DATA_DIR`` reads a local directory instead
(development and tests, e.g. ``site/public/data``). Everything is held in memory as plain
Python rows: the files are small (about 150 KB in all).

If loading fails, the app still runs and reports itself not ready; the next attempt waits
for a backoff (30 s, doubling to 10 minutes), so a failing source is not hit on every
request. The public error message names the file and the check; the detail (exception text,
temporary paths) goes only to the log.
"""

from __future__ import annotations

import hashlib
import json
import logging
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
# The disclosure threshold: a cell resting on fewer respondents is never served with numbers.
MIN_N = 30

log = logging.getLogger(__name__)

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

# Basic column types: "num" (number or null), "bool" (true or false), "str" (text), "str?"
# (text or null). Columns not listed are only required to exist.
_CELL_KINDS = {
    "measure": "str",
    "age_group": "str",
    "sex": "str",
    "estimate": "num",
    "se": "num",
    "ci_low": "num",
    "ci_high": "num",
    "n_unweighted": "num",
    "n_effective": "num",
    "df": "num",
    "precision_flag": "str?",
    "precision_reason": "str?",
    "suppressed": "bool",
}
KINDS: dict[str, dict[str, str]] = {
    "dhs2024_state_prevalence.parquet": {
        "state": "str",
        "state_code": "str",
        "zone": "str",
        **_CELL_KINDS,
        "has_data": "bool",
        "population_2023": "num",
    },
    "dhs2024_national_zone.parquet": {
        "geography_level": "str",
        "geography": "str",
        **_CELL_KINDS,
    },
    "prevalence_comparison.parquet": {
        "figure_id": "str",
        "sort_order": "num",
        "value_percent": "num",
        "ci_low_percent": "num",
        "ci_high_percent": "num",
    },
}

Fetch = Callable[[str], bytes]


class DataError(ValueError):
    """A public file is missing, unreadable or not what the API expects.

    ``str(exc)`` is the public message (file and check, written here, never exception text
    or paths); ``detail`` holds the underlying error, for the log only.
    """

    def __init__(self, message: str, detail: str | None = None) -> None:
        super().__init__(message)
        self.detail = detail


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
            raise DataError(f"{name} failed validation: not readable Parquet", str(exc)) from exc
    missing = [c for c in required if c not in columns]
    if missing:
        raise DataError(f"{name} lacks columns {missing}")
    if not rows:
        raise DataError(f"{name} has no rows")
    _check_kinds(name, rows, KINDS[name])
    return rows


def _is_num(value: Any) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool)


_KIND_CHECKS: dict[str, Callable[[Any], bool]] = {
    "num": lambda v: v is None or _is_num(v),
    "bool": lambda v: isinstance(v, bool),
    "str": lambda v: isinstance(v, str),
    "str?": lambda v: v is None or isinstance(v, str),
}


def _check_kinds(name: str, rows: list[dict[str, Any]], kinds: Mapping[str, str]) -> None:
    for column, kind in kinds.items():
        if not all(_KIND_CHECKS[kind](row[column]) for row in rows):
            raise DataError(f"{name} failed validation: column {column} is not all {kind}")


def _json(name: str, body: bytes) -> Any:
    try:
        return json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DataError(f"{name} failed validation: not valid JSON", str(exc)) from exc


def _check_states(states: Any) -> list[dict[str, Any]]:
    if not isinstance(states, list) or len(states) != N_STATES:
        raise DataError(f"states.json must list {N_STATES} states")
    for state in states:
        if not isinstance(state, dict):
            raise DataError("states.json holds a non-object entry")
        missing = [k for k in STATE_KEYS if k not in state]
        if missing:
            raise DataError(f"states.json entry lacks keys {missing}")
        if not isinstance(state["state"], str) or not isinstance(state["state_code"], str):
            raise DataError("states.json failed validation: state and state_code must be text")
        if state["dhs2024"] is not None and not isinstance(state["dhs2024"], dict):
            raise DataError("states.json failed validation: dhs2024 must be an object or null")
    if len({s["state_code"] for s in states}) != N_STATES:
        raise DataError("states.json state codes are not unique")
    return [_safe_state(s) for s in states]


def small(n: Any) -> bool:
    """True if ``n`` respondents is under the disclosure threshold."""
    return _is_num(n) and n < MIN_N


def _safe_state(state: dict[str, Any]) -> dict[str, Any]:
    """Drop a state's DHS headline if it rests on fewer than ``MIN_N`` respondents (the
    disclosure gate already does this; this is a second check)."""
    headline = state["dhs2024"]
    if headline is not None and small(headline.get("n_unweighted")):
        return {**state, "dhs2024": None}
    return state


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
            raise DataError(f"could not fetch {name}", f"{type(exc).__name__}: {exc}") from exc
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
        """The dataset, loading it if it is missing and the backoff has passed.

        Never waits for another thread's load (which can take minutes on a bad network):
        while one runs, other callers get the current state at once (None, so a 503).
        """
        if self.data is not None:
            return self.data
        if not self._lock.acquire(blocking=False):
            return self.data
        try:
            if self.data is None and self.clock() >= self._next_try:
                self.attempts += 1
                try:
                    self.data = load(self.fetch)
                    self.error = None
                except DataError as exc:
                    self.error = str(exc)
                    log.warning("loading the public data failed: %s (%s)", exc, exc.detail)
                    self._next_try = self.clock() + self._backoff
                    self._backoff = min(self._backoff * 2, BACKOFF_MAX_S)
        finally:
            self._lock.release()
        return self.data

    def retry_in(self) -> float | None:
        """Seconds until the next load attempt, or None once loaded."""
        if self.data is not None:
            return None
        return max(0.0, self._next_try - self.clock())


def store_from_env(env: Mapping[str, str]) -> Store:
    directory = env.get("CURBCUT_DATA_DIR")
    if directory:
        # /status is public, so it names the mode, not the path.
        return Store(dir_fetcher(Path(directory).resolve()), "local directory")
    base = env.get("CURBCUT_DATA_BASE") or DEFAULT_BASE
    return Store(url_fetcher(base), base)
