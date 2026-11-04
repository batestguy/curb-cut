"""Table downloads (P6 item 2): one CSV file and one JSON file for each data table on the site.

Each page builder describes a table once, as a :class:`TableData` (caption, columns, rows of
the values behind the page), and renders both the HTML table and the download files from
that same object, so a download can never disagree with the page. The main page's tables
are drawn in the browser from chart documents and ``spatial.json``; ``build_charts.py``
writes their files from the same JSON (:func:`from_spec`) with a manifest the page reads.

* **CSV** stays plain: a header row and the rows, UTF-8, no comment lines, numbers without
  thousands separators or % signs (the unit, where the label lacks it, is added to the
  header).
* **JSON** carries the same rows with their provenance: caption, columns (label, type,
  decimals, unit), source citations, survey and year, the reuse terms and the page's URL.
  No licence is granted for these files: reuse is subject to the source terms.

Numbers are the values behind the page, not rounded for display (``VALUES_RULE``). Files go
under ``site/public/data/downloads/`` (git-ignored): ``main/``, ``poverty/`` and
``states/<slug>/``, one ``<table-id>.csv`` and ``<table-id>.json`` per table.

JONAPWD's figures ("All rights reserved") never get a download: their tables carry a line
citing the publication instead (``site/src/format.js``, ``citedLine``).
"""

from __future__ import annotations

import csv
import html
import io
import json
import re
import shutil
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

COMMON_TERMS = "Reuse is subject to the source terms; cite the sources."
VALUES_RULE = (
    "Numbers are the values behind the page, not rounded for display (at most 12 significant "
    "digits); the page rounds each column to its 'decimals'. Where the page shows words "
    "instead of figures (a figure not shown), the first value column has the same words and "
    "the row's other figures are empty."
)
# Short table names go into each link's accessible name ("CSV, 2 KB: <name>").
MAX_NAME = 64
TABLE_ID = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")


@dataclass(frozen=True)
class Provenance:
    survey: str
    year: str
    sources: tuple[str, ...]
    terms: str


_DHS_CITATION = (
    "The DHS Program, Nigeria Demographic and Health Survey 2024 (National Population "
    "Commission and ICF), release NG2024DHS; estimates by Curb Cut from the microdata, "
    "disclosure-checked"
)
_DHS_TERMS = (
    'Nigeria DHS 2024: data used only for the registered project "Curb Cut: disability '
    'prevalence and poverty in Nigeria"; no microdata in any tool or dashboard; only '
    "disclosure-checked aggregates are published."
)
_MPI_CITATION = (
    "National Bureau of Statistics, Multidimentional Poverty index Survey 2021 v1.0 "
    "(NGA-NBS-MPI-2021-v1.0)"
)
_MPI_TERMS = (
    "NBS MPI Survey 2021: used solely for reporting aggregated information; no redistribution "
    "of the microdata; an electronic copy of every publication goes to the National Data "
    "Archive."
)
_GHS_CITATION = (
    "National Bureau of Statistics, Nigeria, General Household Survey-Panel Wave 4 "
    "(NGA_2018_GHSP-W4_v03_M) and Wave 5 (NGA_2023_GHSP-W5_v02_M), World Bank Microdata "
    "Library"
)
_GHS_TERMS = (
    "GHS-Panel: public-use files under a confidentiality declaration; no re-identification; "
    "citation required."
)
_P5 = "Curb Cut P5 analysis, pre-registered at https://osf.io/kes3p/"

DHS = Provenance(
    "Nigeria Demographic and Health Survey (DHS)",
    "2024",
    (_DHS_CITATION,),
    f"{COMMON_TERMS} {_DHS_TERMS}",
)
DHS_SPATIAL = Provenance(
    DHS.survey,
    DHS.year,
    (_DHS_CITATION, "Curb Cut spatial analysis of the state estimates (data/public/spatial)"),
    DHS.terms,
)
MPI = Provenance(
    "NBS Multidimensional Poverty Index (MPI) Survey",
    "2021",
    (f"{_MPI_CITATION}; estimates by Curb Cut",),
    f"{COMMON_TERMS} {_MPI_TERMS}",
)
P5_MPI = Provenance(MPI.survey, MPI.year, (_MPI_CITATION, _P5), MPI.terms)
P5_TABLE7 = Provenance(
    MPI.survey,
    MPI.year,
    (
        _MPI_CITATION,
        "National Bureau of Statistics, Nigeria Multidimensional Poverty Index (2022), Table 7",
        _P5,
    ),
    MPI.terms,
)
P5_GHS = Provenance(
    "NBS and World Bank General Household Survey-Panel (GHS-Panel)",
    "2018/19 and 2023/24",
    (_GHS_CITATION, _P5),
    f"{COMMON_TERMS} {_GHS_TERMS}",
)


@dataclass(frozen=True)
class Column:
    label: str
    type: str = "text"  # "text", "number" or "integer"
    decimals: int | None = None  # as shown on the page
    unit: str | None = None

    @property
    def header(self) -> str:
        """The CSV header: the label, with the unit added when the label does not say it."""
        if not self.unit or self.unit in self.label or (self.unit == "%" and "%" in self.label):
            return self.label
        return f"{self.label} ({self.unit})"

    def as_json(self) -> dict[str, Any]:
        out: dict[str, Any] = {"label": self.header, "type": self.type}
        if self.decimals is not None:
            out["decimals"] = self.decimals
        if self.unit:
            out["unit"] = self.unit
        return out


@dataclass(frozen=True)
class TableData:
    """One table as the page shows it: ``rows`` hold the values behind each cell."""

    table_id: str
    name: str
    caption: str
    columns: tuple[Column, ...]
    rows: tuple[tuple[Any, ...], ...]
    provenance: Provenance

    def __post_init__(self) -> None:
        if not TABLE_ID.fullmatch(self.table_id):
            raise ValueError(f"table id {self.table_id!r} is not lowercase-hyphenated")
        if not self.name or len(self.name) > MAX_NAME:
            raise ValueError(f"table name {self.name!r} must be 1-{MAX_NAME} characters")
        for row in self.rows:
            if len(row) != len(self.columns):
                raise ValueError(
                    f"{self.table_id}: a row has {len(row)} cells, not {len(self.columns)}"
                )


def clean(value: Any, column: Column) -> Any:
    """A value as written to both files: binary noise trimmed (12 significant digits), whole
    counts as integers, empty as None. Words stay words."""
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, int | float):
        number = float(f"{float(value):.12g}")
        if column.type == "integer" and number.is_integer():
            return int(number)
        return number
    return str(value)


def _rows(table: TableData) -> list[list[Any]]:
    return [[clean(v, c) for v, c in zip(row, table.columns, strict=True)] for row in table.rows]


def _csv_cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return repr(value)
    return str(value)


def csv_bytes(table: TableData) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\r\n")
    writer.writerow([c.header for c in table.columns])
    for row in _rows(table):
        writer.writerow([_csv_cell(v) for v in row])
    return buffer.getvalue().encode("utf-8")


def json_bytes(table: TableData, page_url: str) -> bytes:
    p = table.provenance
    document = {
        "table": table.table_id,
        "name": table.name,
        "caption": table.caption,
        "page": page_url,
        "survey": p.survey,
        "year": p.year,
        "sources": list(p.sources),
        "terms": p.terms,
        "values": VALUES_RULE,
        "columns": [c.as_json() for c in table.columns],
        "rows": _rows(table),
    }
    return (json.dumps(document, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode(
        "utf-8"
    )


def size_text(n_bytes: int) -> str:
    """Whole kilobytes, at least 1 KB."""
    return f"{max(1, round(n_bytes / 1024))} KB"


def link_line_html(entry: Mapping[str, Any]) -> str:
    """The line under a table: "Download this table: CSV, 2 KB · JSON, 3 KB". Each link's
    accessible name starts with its visible text and then names the table, so names are
    unique on the page and make sense in a screen reader's list of links."""
    links = " · ".join(
        f'<a href="{html.escape(f["href"])}" download '
        f'aria-label="{html.escape(f["text"] + ": " + entry["name"])}">{html.escape(f["text"])}</a>'
        for f in entry["files"]
    )
    return f'<p class="table-download">Download this table: {links}</p>'


@dataclass
class Collector:
    """The downloads of one page. :meth:`add` renders a table's files and returns its link
    line; ``files`` maps each file's path (relative to the downloads folder) to its bytes."""

    page_url: str
    folder: str  # e.g. "poverty" or "states/kano", under the downloads folder
    href_prefix: str  # the downloads folder as the page links it, ending in "/"
    files: dict[str, bytes] = field(default_factory=dict)
    entries: dict[str, dict[str, Any]] = field(default_factory=dict)

    def add(self, table: TableData) -> str:
        if table.table_id in self.entries:
            raise ValueError(f"table id {table.table_id!r} used twice on {self.page_url}")
        if any(e["name"] == table.name for e in self.entries.values()):
            raise ValueError(f"table name {table.name!r} used twice on {self.page_url}")
        files = []
        for fmt, body in (
            ("CSV", csv_bytes(table)),
            ("JSON", json_bytes(table, self.page_url)),
        ):
            path = f"{self.folder}/{table.table_id}.{fmt.lower()}"
            self.files[path] = body
            files.append(
                {
                    "format": fmt,
                    "href": f"{self.href_prefix}{path}",
                    "bytes": len(body),
                    "text": f"{fmt}, {size_text(len(body))}",
                }
            )
        entry = {"name": table.name, "files": files}
        self.entries[table.table_id] = entry
        return link_line_html(entry)

    def check_linked(self, page_html: str) -> None:
        """Refuse files for a table the page does not show (every file must be linked)."""
        missing = [
            f["href"]
            for e in self.entries.values()
            for f in e["files"]
            if f'href="{html.escape(f["href"])}"' not in page_html
        ]
        if missing:
            raise ValueError(f"downloads not linked from {self.page_url}: {missing}")

    def write(self, downloads_dir: Path) -> None:
        """Replace this page's folder with its files."""
        target = downloads_dir / self.folder
        if target.exists():
            shutil.rmtree(target)
        target.mkdir(parents=True)
        for path, body in self.files.items():
            (downloads_dir / path).write_bytes(body)


def from_spec(
    spec: Mapping[str, Any], table_id: str, name: str, provenance: Provenance
) -> TableData:
    """A table spec as the site's JavaScript renders it (``renderTable`` in
    ``site/src/format.js``; a chart document's ``table``): caption, columns with label, type
    ("text", "number", "integer" or "percent") and decimals, and rows."""
    columns = []
    for c in spec["columns"]:
        kind = c.get("type", "text")
        label = str(c["label"])
        unit = "%" if "(%)" in label else None
        if kind == "percent":
            columns.append(Column(label, "number", int(c.get("decimals", 1)), unit or "%"))
        elif kind == "number":
            columns.append(Column(label, "number", int(c.get("decimals", 1)), unit))
        elif kind == "integer":
            columns.append(Column(label, "integer", 0, unit))
        else:
            columns.append(Column(label))
    return TableData(
        table_id,
        name,
        str(spec["caption"]),
        tuple(columns),
        tuple(tuple(row) for row in spec["rows"]),
        provenance,
    )


def write_manifest(collector: Collector, downloads_dir: Path) -> Path:
    """The main page's downloads (``<folder>/index.json``): table id -> name and files."""
    collector.write(downloads_dir)
    path = downloads_dir / collector.folder / "index.json"
    path.write_text(
        json.dumps({"tables": collector.entries}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return path


def parse_csv(body: bytes) -> list[list[str]]:
    """Read a written CSV back (for tests and checks)."""
    return list(csv.reader(io.StringIO(body.decode("utf-8"), newline="")))


def same_rows(csv_rows: Sequence[Sequence[str]], json_rows: Sequence[Sequence[Any]]) -> bool:
    """True when a CSV's body rows hold exactly the JSON rows' values."""
    if len(csv_rows) != len(json_rows):
        return False
    for c_row, j_row in zip(csv_rows, json_rows, strict=True):
        if len(c_row) != len(j_row):
            return False
        for c, j in zip(c_row, j_row, strict=True):
            if j is None:
                if c != "":
                    return False
            elif isinstance(j, int | float) and not isinstance(j, bool):
                if float(c) != float(j):
                    return False
            elif c != str(j):
                return False
    return True
