"""Build ``site/data-dictionary.html``: every public data file, column by column, as plain HTML.

Run after ``export_marts.py``, from the repo root:
``uv run python packages/transform/scripts/build_data_dictionary.py``.

Reads, all public:

* the dbt marts' YAML (``packages/transform/models/marts/_marts.yml``): each column's
  ``description`` and unit (``config.meta.unit``), and each mart's citations and terms
  (``config.meta.sources``);
* ``packages/transform/public_files.yml``: which mart feeds which public file, the JSON
  fields no mart column covers, the downloads' shared structure, the API's endpoints;
* the warehouse (read-only), for each mart's actual columns;
* the exported files in ``site/public/data/``, for each file's actual columns, types, rows
  and size.

It reads the YAML directly rather than dbt's ``target/manifest.json``. The YAML is where the
descriptions are written, and it needs no dbt run: the pytest job has no warehouse, and in
the data job the manifest is rewritten by whichever dbt command ran last (the fixture build,
then ``dbt docs generate``). The descriptions use no Jinja (``{{ doc() }}``), which only dbt
would render; the build refuses one that does.

Writes ``site/data-dictionary.html`` (git-ignored; Vite takes it as an input). The page has no
script, so the browser's find works on all of it. Every file has a stable anchor (its name,
lower case, other characters as hyphens: ``#dhs2024-state-prevalence-parquet``) and so does
every column (``#dhs2024-state-prevalence-parquet--estimate``), for other pages to link.

The build fails (exit 1) if a column of a public file, or of a mart behind one, has no
description; if a description names a column the mart or the file does not have; or if the
downloads' description no longer matches what ``downloads.py`` writes.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import sys
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType
from typing import Any

import duckdb
import yaml

ROOT = Path(__file__).resolve().parents[3]
TRANSFORM = ROOT / "packages" / "transform"
DEFAULT_MARTS = TRANSFORM / "models" / "marts" / "_marts.yml"
DEFAULT_REGISTRY = TRANSFORM / "public_files.yml"
DEFAULT_DB = ROOT / "data" / "curbcut.duckdb"
DEFAULT_DATA = ROOT / "site" / "public" / "data"
DEFAULT_PAGE = ROOT / "site" / "data-dictionary.html"
# The page is long by nature but has no script and no images; keep it light on a phone.
HTML_BUDGET = 200 * 1024
# A column with no unit: a dash on screen, "not applicable" for screen readers.
NO_UNIT = (
    '<span aria-hidden="true">\u2013</span><span class="visually-hidden">not applicable</span>'
)


def _load(name: str) -> ModuleType:
    """Sibling scripts are not a package; load them by path."""
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(f"{name}.py"))
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


pages = _load("build_state_pages")
downloads = _load("downloads")
esc = pages.esc


class DictionaryError(ValueError):
    """The dictionary cannot be built; the message lists every problem found."""


# --- Inputs ---------------------------------------------------------------------------------


@dataclass(frozen=True)
class Described:
    description: str
    unit: str | None = None


@dataclass
class Mart:
    name: str
    columns: dict[str, Described]  # only columns with a description
    listed: list[str]  # every column the YAML names, described or not
    sources: list[dict[str, str]]


def _text(value: Any) -> str:
    return " ".join(str(value).split()) if value is not None else ""


def load_marts(path: Path) -> dict[str, Mart]:
    """Each mart's described columns, units and sources, from the dbt YAML."""
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    marts: dict[str, Mart] = {}
    for model in document.get("models", []):
        meta = (model.get("config") or {}).get("meta") or {}
        columns: dict[str, Described] = {}
        listed: list[str] = []
        for column in model.get("columns") or []:
            listed.append(column["name"])
            description = _text(column.get("description"))
            if description:
                unit = ((column.get("config") or {}).get("meta") or {}).get("unit")
                columns[column["name"]] = Described(description, _text(unit) or None)
        marts[model["name"]] = Mart(model["name"], columns, listed, list(meta.get("sources") or []))
    return marts


def _described(value: Any) -> Described:
    if isinstance(value, Mapping):
        unit = _text(value.get("unit")) or None
        return Described(_text(value.get("description")), unit)
    return Described(_text(value))


@dataclass
class PublicFile:
    file: str
    title: str
    about: str
    marts: dict[str, str]  # path prefix -> mart
    fields: dict[str, Described]
    maps: dict[str, str]
    link: bool = True
    sources_from: list[str] = field(default_factory=list)
    made_from: str = ""  # HTML; by default the marts it is made from

    @property
    def is_json(self) -> bool:
        return self.file.endswith(".json")

    @property
    def anchor(self) -> str:
        return slug(self.file)

    def all_marts(self) -> list[str]:
        return list(dict.fromkeys([*self.marts.values(), *self.sources_from]))


@dataclass
class Registry:
    files: list[PublicFile]
    download_fields: dict[str, Described]
    api: dict[str, Any]
    other_files: list[dict[str, str]]


def load_registry(path: Path) -> Registry:
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    files = [
        PublicFile(
            file=f["file"],
            title=_text(f["title"]),
            about=_text(f["about"]),
            marts=dict(f.get("marts") or {}),
            fields={k: _described(v) for k, v in (f.get("fields") or {}).items()},
            maps=dict(f.get("maps") or {}),
            link=bool(f.get("link", True)),
            sources_from=list(f.get("sources_from") or []),
            made_from=_text(f.get("made_from")),
        )
        for f in document["files"]
    ]
    return Registry(
        files,
        {k: _described(v) for k, v in document["downloads"]["fields"].items()},
        document["api"],
        list(document.get("other_files") or []),
    )


def slug(text: str) -> str:
    """Stable anchor: lower case, every run of other characters one hyphen."""
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


# --- Reading the files ----------------------------------------------------------------------


@dataclass
class Column:
    path: str
    type: str


@dataclass
class FileFacts:
    columns: list[Column]
    rows: int | None
    bytes: int


FRIENDLY = {
    "VARCHAR": "text",
    "DOUBLE": "number",
    "FLOAT": "number",
    "DECIMAL": "number",
    "BIGINT": "whole number",
    "INTEGER": "whole number",
    "SMALLINT": "whole number",
    "TINYINT": "whole number",
    "HUGEINT": "whole number",
    "BOOLEAN": "true or false",
    "DATE": "date",
}


def parquet_facts(path: Path) -> FileFacts:
    with duckdb.connect() as con:
        described = con.execute("describe select * from read_parquet(?)", [path.as_posix()])
        columns = [
            Column(name, f"{friendly(kind)} ({kind})") for name, kind, *_ in described.fetchall()
        ]
        row = con.execute("select count(*) from read_parquet(?)", [path.as_posix()]).fetchone()
    return FileFacts(columns, int(row[0]) if row else 0, path.stat().st_size)


def _kind(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true or false"
    if isinstance(value, int):
        return "whole number"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "text"
    return type(value).__name__


def _type_text(kinds: set[str]) -> str:
    """Kinds as words ("number or null"); whole numbers beside numbers read as numbers."""
    values = kinds - {"null"}
    if {"number", "whole number"} <= values:
        values -= {"whole number"}
    order = ["text", "number", "whole number", "true or false", "object", "list"]
    words = sorted(values, key=lambda k: order.index(k) if k in order else len(order))
    text = " or ".join(words) if words else "null (in this build)"
    return f"{text} or null" if words and "null" in kinds else text


def json_paths(document: Any, maps: Mapping[str, str]) -> dict[str, set[str]]:
    """Every path in a JSON document with the kinds of value found there. Lists of plain
    values are one path ("list of text"); objects named in ``maps`` are keyed by a
    placeholder (``estimates.{estimate_id}``)."""
    found: dict[str, set[str]] = {}

    def add(path: str, kind: str) -> None:
        found.setdefault(path, set()).add(kind)

    def walk(node: Any, path: str) -> None:
        if isinstance(node, dict):
            if path:
                add(path, "object")
            if path in maps:
                for value in node.values():
                    walk(value, f"{path}.{{{maps[path]}}}")
            else:
                for key, value in node.items():
                    walk(value, f"{path}.{key}" if path else str(key))
        elif isinstance(node, list):
            if all(not isinstance(item, dict | list) for item in node):
                kinds = {_kind(item) for item in node}
                add(path, f"list of {_type_text(kinds)}" if kinds else "list (empty in this build)")
            else:
                if path:  # the document itself needs no row; its items are "[]"
                    add(path, "list")
                for item in node:
                    walk(item, f"{path}[]")
        else:
            add(path, _kind(node))

    walk(document, "")
    return found


def json_facts(path: Path, maps: Mapping[str, str]) -> FileFacts:
    document = json.loads(path.read_text(encoding="utf-8"))
    found = json_paths(document, maps)
    columns = [Column(p, _type_text(kinds)) for p, kinds in found.items()]
    rows = len(document) if isinstance(document, list) else None
    return FileFacts(columns, rows, path.stat().st_size)


def mart_columns(con: duckdb.DuckDBPyConnection, mart: str) -> dict[str, str]:
    """The mart's columns in the warehouse, with their types."""
    rows = con.execute(
        "select column_name, data_type from information_schema.columns where table_name = ? "
        "order by ordinal_position",
        [mart],
    ).fetchall()
    return {name: kind for name, kind in rows}


def friendly(kind: str) -> str:
    return FRIENDLY.get(kind.split("(")[0], kind.lower())


# --- Checks and resolution ------------------------------------------------------------------


@dataclass
class Row:
    path: str
    type: str
    described: Described
    origin: str  # the mart, or "" for a description in public_files.yml


@dataclass
class FileSection:
    spec: PublicFile
    facts: FileFacts
    rows: list[Row]
    sources: list[dict[str, str]]


def check_marts(
    marts: Mapping[str, Mart], names: Iterable[str], actual: Mapping[str, Mapping[str, str]]
) -> list[str]:
    """Every column of each mart has a description; the YAML names no column the mart lacks."""
    problems = []
    for name in names:
        if name not in marts:
            problems.append(f"{name}: not in the marts' YAML")
            continue
        if name not in actual or not actual[name]:
            problems.append(f"{name}: not in the warehouse")
            continue
        mart = marts[name]
        for column in actual[name]:
            if column not in mart.columns:
                problems.append(f"{name}.{column}: no description")
        for column in mart.listed:
            if column not in actual[name]:
                problems.append(f"{name}.{column}: described, but the mart has no such column")
        for column, described in mart.columns.items():
            if "{{" in described.description or "{%" in described.description:
                problems.append(f"{name}.{column}: Jinja in a description is not rendered here")
        if not mart.sources:
            problems.append(f"{name}: no config.meta.sources")
    return problems


def resolve(
    spec: PublicFile,
    facts: FileFacts,
    marts: Mapping[str, Mart],
    types: Mapping[str, Mapping[str, str]] | None = None,
) -> tuple[list[Row], list[str]]:
    """Each column of the file with its description; problems for any without one, or for
    a description in public_files.yml naming a field the file does not have. A JSON field
    that is null everywhere in this build takes its type from the mart (``types``)."""
    problems = []
    rows = []
    prefixes = sorted(spec.marts.items(), key=lambda kv: len(kv[0]), reverse=True)
    paths = {c.path for c in facts.columns}
    for column in facts.columns:
        described: Described | None = spec.fields.get(column.path)
        origin = ""
        if described is None:
            for prefix, mart in prefixes:
                rest = column.path[len(prefix) :]
                if column.path.startswith(prefix) and rest and "." not in rest and "[" not in rest:
                    described = marts[mart].columns.get(rest) if mart in marts else None
                    origin = mart
                    break
        if described is None or not described.description:
            problems.append(f"{spec.file}: {column.path} has no description")
            continue
        kind = column.type
        mart_type = (types or {}).get(origin, {}).get(column.path.rsplit(".", 1)[-1])
        if kind.startswith("null") and mart_type:
            kind = f"{friendly(mart_type)} or null"
        rows.append(Row(column.path, kind, described, origin))
    for path in spec.fields:
        if path not in paths:
            problems.append(f"{spec.file}: public_files.yml describes {path}, which the file lacks")
    return rows, problems


def check_downloads(fields: Mapping[str, Described]) -> list[str]:
    """The downloads' JSON keys, as downloads.py writes them, against their descriptions."""
    sample = downloads.TableData(
        "sample",
        "Sample",
        "Sample",
        (
            downloads.Column("Name"),
            downloads.Column("Value", "number", 1, "%"),
        ),
        (("a", 1.0),),
        downloads.DHS,
    )
    document = json.loads(downloads.json_bytes(sample, "https://example.invalid/"))
    found = set(json_paths(document, {}))
    problems = [f"downloads: {p} has no description" for p in sorted(found - set(fields))]
    problems += [
        f"downloads: public_files.yml describes {p}, which downloads.py does not write"
        for p in sorted(set(fields) - found)
    ]
    return problems


def collect(
    registry: Registry,
    marts: Mapping[str, Mart],
    con: duckdb.DuckDBPyConnection,
    data_dir: Path,
) -> list[FileSection]:
    """Read every public file and check it against its descriptions. Raises
    :class:`DictionaryError` listing every problem."""
    problems: list[str] = []
    names = list(dict.fromkeys(m for f in registry.files for m in f.all_marts()))
    actual = {name: mart_columns(con, name) for name in names}
    problems += check_marts(marts, names, actual)
    problems += check_downloads(registry.download_fields)
    known = {f.file for f in registry.files}
    for endpoint in registry.api["endpoints"]:
        for name in endpoint["files"]:
            if name not in known:
                problems.append(f"API {endpoint['path']}: {name} is not a public file")
    sections = []
    for spec in registry.files:
        path = data_dir / spec.file
        if not path.exists():
            problems.append(f"{spec.file}: not found in {data_dir}")
            continue
        facts = json_facts(path, spec.maps) if spec.is_json else parquet_facts(path)
        rows, found = resolve(spec, facts, marts, actual)
        problems += found
        sources: list[dict[str, str]] = []
        for mart in spec.all_marts():
            for source in marts[mart].sources if mart in marts else []:
                if source not in sources:
                    sources.append(source)
        sections.append(FileSection(spec, facts, rows, sources))
    if problems:
        raise DictionaryError("\n".join(problems))
    return sections


# --- The page -------------------------------------------------------------------------------


def size_text(n_bytes: int) -> str:
    return downloads.size_text(n_bytes)


def column_anchor(file_anchor: str, path: str) -> str:
    """``#states-json--item-dhs2024-estimate``: a list's items are "item"."""
    return f"{file_anchor}--{slug(path.replace('[]', '.item'))}"


def table_html(caption: str, head: Sequence[str], rows: Sequence[Sequence[str]]) -> str:
    """A captioned table in the site's scroll wrapper (the caption is the Tab stop). The first
    cell of each row is its header and may carry an ``id``: pass it as ``(id, html)``."""
    thead = "".join(f'<th scope="col">{esc(h)}</th>' for h in head)
    body = []
    for row in rows:
        first, *rest = row
        body.append(f"<tr>{first}" + "".join(f"<td>{cell}</td>" for cell in rest) + "</tr>")
    table = (
        f"<table><caption>{esc(caption)}</caption><thead><tr>{thead}</tr></thead>"
        f"<tbody>{''.join(body)}</tbody></table>"
    )
    return pages.wide_table(table, caption)


def name_html(name: str) -> str:
    """A file or column name that may wrap only after "_", ".", "/" or a bracket, never
    inside a word (``<wbr>`` adds no character, so the browser's find still matches)."""
    return re.sub(r"([_./\]}])", r"\g<1><wbr>", esc(name))


def row_header(anchor: str, path: str) -> str:
    return f'<th scope="row" id="{esc(anchor)}"><code>{name_html(path)}</code></th>'


def sources_html(sources: Sequence[Mapping[str, str]]) -> str:
    items = []
    for s in sources:
        cite = esc(_text(s["citation"]))
        url = s.get("url")
        linked = f'<a href="{esc(url)}">{cite}</a>' if url else cite
        terms = _text(s.get("terms"))
        items.append(f"<li>{linked}. {esc(terms)}</li>" if terms else f"<li>{linked}.</li>")
    return f'<ul class="sentences">{"".join(items)}</ul>'


def file_section(section: FileSection) -> str:
    spec, facts = section.spec, section.facts
    anchor = spec.anchor
    kind = "JSON" if spec.is_json else "Parquet"
    size = f"{kind}, {size_text(facts.bytes)}"
    if facts.rows is not None:
        noun = ("entry", "entries") if spec.is_json else ("row", "rows")
        size += f", {facts.rows:,} {noun[0] if facts.rows == 1 else noun[1]}"
    if spec.link:
        where = f'<a href="./data/{esc(spec.file)}">{esc(spec.file)}</a> ({size})'
    else:
        where = None
    facts_line = (
        f"File: {where}"
        if where
        else "Not offered for download: JONAPWD's tables by type are cited from an "
        "all-rights-reserved publication, and the site reads them only for its own tables "
        "and charts"
    )
    made_from = spec.made_from or (
        "the warehouse's " + " and ".join(f"<code>{esc(m)}</code>" for m in spec.marts.values())
    )
    noun = "fields" if spec.is_json else "columns"
    rows = [
        (
            row_header(column_anchor(anchor, r.path), r.path),
            esc(r.type),
            esc(r.described.description),
            esc(r.described.unit) if r.described.unit else NO_UNIT,
        )
        for r in section.rows
    ]
    return f"""<section aria-labelledby="{anchor}">
<h2 id="{anchor}">{name_html(spec.file)}: {esc(spec.title)}</h2>
<p>{esc(spec.about)}</p>
<p class="file-facts">{facts_line}. Made from {made_from}.</p>
<h3 id="{anchor}--sources">Sources and terms</h3>
{sources_html(section.sources)}
{table_html(f"The {len(rows)} {noun} of {spec.file}", ("Name", "Type", "Meaning", "Units"), rows)}
</section>"""


def downloads_section(fields: Mapping[str, Described]) -> str:
    anchor = "table-downloads"
    rows = [
        (
            row_header(column_anchor(anchor, path), path),
            esc(d.description),
            esc(d.unit) if d.unit else NO_UNIT,
        )
        for path, d in fields.items()
    ]
    return f"""<section aria-labelledby="{anchor}">
<h2 id="{anchor}">Table downloads (CSV and JSON)</h2>
<p>Under every data table on the site is a line "Download this table: CSV, n KB · JSON,
n KB". There is one pair of files per table, so there are hundreds; all share one structure,
described here once. They sit under <code>data/downloads/</code>: <code>main/</code> for the
main page, <code>poverty/</code> for the poverty page and <code>states/&lt;state&gt;/</code>
for each state page (for example <code>states/akwa-ibom/</code>), one
<code>&lt;table&gt;.csv</code> and one <code>&lt;table&gt;.json</code> for each table.</p>
<ul class="sentences">
<li>The CSV is plain: a header row, then the rows, in UTF-8, with no comment lines. Numbers
have no thousands separators or % signs; where a heading lacks the unit, the unit is added in
brackets.</li>
<li>The JSON has the same rows with their provenance, in the fields below.</li>
<li>{esc(downloads.VALUES_RULE)}</li>
<li>JONAPWD's tables have no download: they carry a citation line instead.</li>
</ul>
{table_html("The fields of every table's JSON download", ("Name", "Meaning", "Units"), rows)}
</section>"""


API_COLUMNS = ("Endpoint", "What it returns", "Files")


def api_section(api: Mapping[str, Any], files: Sequence[PublicFile]) -> str:
    anchor = "api"
    by_name = {f.file: f for f in files}
    rows = []
    for e in api["endpoints"]:
        served = ", ".join(f'<a href="#{by_name[n].anchor}">{esc(n)}</a>' for n in e["files"])
        rows.append(
            (
                row_header(column_anchor(anchor, e["path"]), e["path"]),
                esc(_text(e["what"])),
                served,
            )
        )
    return f"""<section aria-labelledby="{anchor}">
<h2 id="{anchor}">The API</h2>
<p>An optional, read-only JSON API serves some of these files at
<code>{esc(api["url"])}</code>. Its fields are the files' fields, described above, inside a
small envelope (a count, the units and the source). Its interactive documentation is at
<a href="{esc(api["docs"])}">curb-cut-api.onrender.com/docs</a>. This site never calls it: every
figure is in the files themselves. It runs on a free plan, so the first request after a quiet
spell can take about a minute.</p>
{table_html("API endpoints and the files each one serves", API_COLUMNS, rows)}
</section>"""


def other_files_section(other: Sequence[Mapping[str, str]]) -> str:
    items = "".join(
        f"<li><code>{esc(o['path'])}</code>: {esc(_text(o['about']))}</li>" for o in other
    )
    return f"""<section aria-labelledby="other-files">
<h2 id="other-files">Other files</h2>
<p>The site also serves these, which are not data tables:</p>
<ul class="sentences">{items}</ul>
</section>"""


INTRO = """<p>Every data file this site publishes, column by column: what each column means, its
type and its units, where the figures come from and on what terms they may be reused. The
columns' meanings are written once, with the data warehouse's tables, and this page is built
from them, so it changes when the data do. Use your browser's find (Ctrl+F, or Cmd+F on a
Mac) to look up a column.</p>
<section aria-labelledby="conventions">
<h2 id="conventions">How to read the figures</h2>
<ul class="sentences">
<li><strong>Proportions and percentages.</strong> Survey estimates in the data files are
proportions from 0 to 1 (0.03 is 3%). The comparison figures
(<code>prevalence_comparison.parquet</code>, and <code>comparison</code> in
<code>prevalence.json</code>) are percentages from 0 to 100. The Units column says which.</li>
<li><strong>Intervals.</strong> Every interval is a 95% confidence interval.</li>
<li><strong>Suppressed cells.</strong> No survey estimate rests on fewer than 30 unweighted
respondents. Such a survey cell keeps its row, with <code>suppressed</code> true and its
estimate, standard error, interval, counts and degrees of freedom empty (null); so does a cell
withheld so that a small neighbouring cell cannot be worked out by subtraction. A poverty
(model) estimate is suppressed when either group compared has fewer than 30 households or
people: its estimate, standard error, interval, p-values, <code>mu0</code> and both group
counts are then null, while <code>n</code> and <code>display_factor</code> stay. Missing
numbers are never estimated or filled in. JONAPWD's figures are assumptions, not survey cells,
so these rules do not apply to them.</li>
<li><strong>Precision.</strong> <code>precision_flag</code> says how far an estimate can be
trusted (reliable, review or unreliable, under the US National Center for Health Statistics'
standards for proportions plus one stricter rule of our own); <code>precision_reason</code>
says which rule applied.</li>
<li><strong>JONAPWD's figures are an assumption, not a count.</strong> JONAPWD applied the
global 15% disability rate to population projections; nobody was counted.</li>
<li><strong>Poverty results are adjusted associations, not causal effects.</strong></li>
<li><strong>Licence.</strong> The code is MIT-licensed. No licence is granted for the
figures: reuse is subject to each source's terms, given with each file; cite the sources.</li>
</ul>
</section>"""


def nav_html() -> str:
    return (
        '<nav class="site-nav" aria-label="Site"><ul>'
        '<li><a href="./">Main page</a></li>'
        '<li><a href="./states/">State pages</a></li>'
        '<li><a href="./explorer.html">Data explorer</a></li>'
        '<li><a href="./sensitivity.html">Assumed rate vs survey</a></li>'
        '<li><a href="./poverty.html">Disability and poverty</a></li>'
        '<li><a href="./methodology.html">Methodology</a></li>'
        '<li><a href="./data-dictionary.html" aria-current="page">Data dictionary</a></li>'
        "</ul></nav>"
    )


def page_html(sections: Sequence[FileSection], registry: Registry, site_url: str) -> str:
    if not site_url.endswith("/"):
        site_url += "/"
    contents = "".join(
        f'<li><a href="#{s.spec.anchor}">{esc(s.spec.file)}</a>: {esc(s.spec.title)}</li>'
        for s in sections
    )
    contents += (
        '<li><a href="#table-downloads">Table downloads (CSV and JSON)</a></li>'
        '<li><a href="#api">The API</a></li>'
        '<li><a href="#other-files">Other files</a></li>'
    )
    head = pages.head_html(
        title="Data dictionary: Curb Cut",
        description=(
            "Every public data file of Curb Cut, column by column: meaning, type, units, "
            "source and terms, for the DHS 2024 disability estimates, the comparison, the "
            "spatial results and the poverty analysis."
        ),
        canonical=f"{site_url}data-dictionary.html",
    ).replace('href="../src/style.css"', 'href="./src/style.css"')
    body = "\n".join(file_section(s) for s in sections)
    return f"""{head}<body>
<a class="skip-link" href="#main">Skip to main content</a>
<div class="flag-band" aria-hidden="true"></div>
<header class="site-header"><p class="site-name"><a href="./">Curb Cut</a></p>
{nav_html()}</header>
<main id="main" tabindex="-1" class="dictionary-page">
<h1>Data dictionary</h1>
{INTRO}
<nav aria-labelledby="contents-heading">
<h2 id="contents-heading">Files on this page</h2>
<ul class="sentences">{contents}</ul>
</nav>
{body}
{downloads_section(registry.download_fields)}
{api_section(registry.api, registry.files)}
{other_files_section(registry.other_files)}
</main>
<footer class="site-footer">
<h2 class="footer-heading">Accessibility and feedback</h2>
{pages.REPORT_HTML}
<p><a href="./methodology.html">Methodology: definitions, sources and limits</a>.
<a href="./">Back to the main page</a>. Source code and data notes:
<a href="{pages.REPO}">github.com/batestguy/curb-cut</a>.</p>
</footer>
</body>
</html>
"""


def build(
    db: Path,
    data_dir: Path,
    page: Path,
    *,
    marts_yml: Path = DEFAULT_MARTS,
    registry_yml: Path = DEFAULT_REGISTRY,
    site_url: str = pages.DEFAULT_SITE_URL,
) -> str:
    """Check everything, then write the page. Raises :class:`DictionaryError`."""
    marts = load_marts(marts_yml)
    registry = load_registry(registry_yml)
    with duckdb.connect(str(db), read_only=True) as con:
        sections = collect(registry, marts, con, data_dir)
    out = page_html(sections, registry, site_url)
    ids = re.findall(r'\bid="([^"]+)"', out)
    duplicates = sorted({i for i in ids if ids.count(i) > 1})
    if duplicates:
        raise DictionaryError(f"duplicate anchors: {', '.join(duplicates)}")
    size = len(out.encode("utf-8"))
    if size > HTML_BUDGET:
        raise DictionaryError(f"the page is {size:,} bytes, over the {HTML_BUDGET:,}-byte budget")
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text(out, encoding="utf-8", newline="\n")
    return out


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build site/data-dictionary.html.")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--page", type=Path, default=DEFAULT_PAGE)
    parser.add_argument("--marts-yml", type=Path, default=DEFAULT_MARTS)
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--site-url", default=os.environ.get("SITE_URL", pages.DEFAULT_SITE_URL))
    args = parser.parse_args(argv)
    try:
        out = build(
            args.db,
            args.data_dir,
            args.page,
            marts_yml=args.marts_yml,
            registry_yml=args.registry,
            site_url=args.site_url,
        )
    except (DictionaryError, duckdb.Error, OSError) as error:
        print(f"Data dictionary failed:\n{error}", file=sys.stderr)
        return 1
    print(f"wrote {args.page} ({len(out.encode('utf-8')):,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
