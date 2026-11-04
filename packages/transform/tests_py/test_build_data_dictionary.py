"""Tests for scripts/build_data_dictionary.py (P6: the data dictionary).

The build is exercised on a small synthetic warehouse and data folder written here (two marts,
a Parquet file and a JSON file with a mart prefix, its own fields and a keyed object), with
marts YAML and a registry of the same shape as the real ones. The real YAML and registry are
checked statically: every public mart fully described, the file list in step with
export_marts.py and the API. No network, no real survey figure.
"""

from __future__ import annotations

import importlib.util
import itertools
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

import duckdb
import pytest
import yaml

ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = ROOT / "packages" / "transform" / "scripts"


def _load(name: str):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


dd = _load("build_data_dictionary")
export = _load("export_marts")
poverty_page = _load("build_poverty_page")

MARTS = {
    "version": 2,
    "models": [
        {
            "name": "mart_cells",
            "config": {
                "meta": {
                    "sources": [
                        {
                            "citation": "Survey A",
                            "url": "https://example.test/a",
                            "terms": "Aggregates only.",
                        }
                    ]
                }
            },
            "columns": [
                {"name": "state", "description": "State name."},
                {
                    "name": "estimate",
                    "description": "Share with the difficulty.",
                    "config": {"meta": {"unit": "proportion (0 to 1)"}},
                },
                {"name": "suppressed", "description": "True when removed."},
            ],
        },
        {
            "name": "mart_results",
            "config": {"meta": {"sources": [{"citation": "Analysis B", "terms": "Cite it."}]}},
            "columns": [
                {"name": "label", "description": "The result in words."},
                {"name": "value", "description": "The result.", "data_tests": ["not_null"]},
            ],
        },
    ],
}


def _registry() -> dict[str, Any]:
    real = yaml.safe_load(dd.DEFAULT_REGISTRY.read_text(encoding="utf-8"))
    return {
        "files": [
            {
                "file": "cells.parquet",
                "title": "Cells",
                "about": "The cells.",
                "marts": {"": "mart_cells"},
            },
            {
                "file": "hidden.parquet",
                "title": "Cited only",
                "about": "Not offered.",
                "marts": {"": "mart_cells"},
                "link": False,
            },
            {
                "file": "results.json",
                "title": "Results",
                "about": "Results by id.",
                "marts": {"results.{result_id}.": "mart_results"},
                "maps": {"results": "result_id"},
                "fields": {
                    "note": "What the results are.",
                    "results": "Every result, by id.",
                    "results.{result_id}": "One result.",
                    "tags": "Labels, as a list.",
                    "range": {"description": "Lowest and highest.", "unit": "points"},
                    "range.min": {"description": "Lowest.", "unit": "points"},
                },
            },
        ],
        "downloads": real["downloads"],
        "api": {
            "url": "https://api.example.test",
            "docs": "https://api.example.test/docs",
            "endpoints": [
                {"path": "/cells", "what": "The cells.", "files": ["cells.parquet"]},
                {"path": "/results", "what": "The results.", "files": ["results.json"]},
            ],
        },
        "other_files": [{"path": "data/charts/", "about": "Chart documents."}],
    }


RESULTS = {
    "note": "Synthetic.",
    "results": {
        "a": {"label": "First", "value": 1.5},
        "b": {"label": "Second", "value": None},
    },
    "tags": ["x", "y"],
    "range": {"min": 0.5},
}


@pytest.fixture
def inputs(tmp_path: Path) -> dict[str, Path]:
    """A synthetic warehouse, data folder, marts YAML and registry."""
    db = tmp_path / "warehouse.duckdb"
    data = tmp_path / "data"
    data.mkdir()
    with duckdb.connect(str(db)) as con:
        con.execute(
            "create table mart_cells as select * from (values ('Kano', 0.05::double, false), "
            "('Edo', null, true)) t(state, estimate, suppressed)"
        )
        con.execute(
            "create table mart_results as select * from (values ('First', 1.5)) t(label, value)"
        )
        for name in ("cells", "hidden"):
            target = (data / f"{name}.parquet").as_posix()
            con.execute(f"copy (select * from mart_cells) to '{target}' (format parquet)")
    (data / "results.json").write_text(json.dumps(RESULTS), encoding="utf-8")
    marts = tmp_path / "_marts.yml"
    marts.write_text(yaml.safe_dump(MARTS, sort_keys=False), encoding="utf-8")
    registry = tmp_path / "public_files.yml"
    registry.write_text(yaml.safe_dump(_registry(), sort_keys=False), encoding="utf-8")
    return {"db": db, "data": data, "marts": marts, "registry": registry, "tmp": tmp_path}


def _build(inputs: dict[str, Path]) -> str:
    return dd.build(
        inputs["db"],
        inputs["data"],
        inputs["tmp"] / "site" / "data-dictionary.html",
        marts_yml=inputs["marts"],
        registry_yml=inputs["registry"],
        site_url="https://x.test/cc",
    )


def _edit_yaml(path: Path, change) -> None:
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    change(document)
    path.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")


# --- A successful build ---------------------------------------------------------------------


def test_builds_from_synthetic_inputs(inputs: dict[str, Path], capsys) -> None:
    page = inputs["tmp"] / "out" / "data-dictionary.html"
    argv = [
        "--db",
        str(inputs["db"]),
        "--data-dir",
        str(inputs["data"]),
        "--page",
        str(page),
        "--marts-yml",
        str(inputs["marts"]),
        "--registry",
        str(inputs["registry"]),
    ]
    assert dd.main(argv) == 0
    assert "wrote" in capsys.readouterr().out
    html = page.read_text(encoding="utf-8")
    # Every column of every file, with its meaning, type and unit.
    for anchor, meaning in (
        ("cells-parquet--state", "State name."),
        ("cells-parquet--estimate", "Share with the difficulty."),
        ("results-json--results-result-id-label", "The result in words."),
        ("results-json--results-result-id-value", "The result."),
        ("results-json--range-min", "Lowest."),
        ("results-json--tags", "Labels, as a list."),
    ):
        assert re.search(rf'<th scope="row" id="{anchor}"><code>.+?</code></th>', html), anchor
        assert meaning in html
    assert "<td>number (DOUBLE)</td><td>Share with the difficulty.</td><td>proportion (0 to 1)" in (
        html
    )
    assert "<td>list of text</td>" in html
    # Names wrap only after "_" or ".", never inside a word.
    assert "<code>results.<wbr>{result_<wbr>id}<wbr>.<wbr>label</code>" in html
    assert "<td>number or null</td><td>The result.</td><td>none</td>" in html
    # Sources and terms from the marts' meta; the link to each file, except a cited one.
    assert '<a href="https://example.test/a">Survey A</a>. Aggregates only.' in html
    assert '<a href="./data/cells.parquet">cells.parquet</a> (Parquet, 1 KB, 2 rows)' in html
    assert 'href="./data/hidden.parquet"' not in html
    assert "<code>data/hidden.parquet</code>" in html
    # The downloads' structure and the API, which the site does not call.
    assert 'id="table-downloads--columns-item-label"' in html
    assert '<a href="https://api.example.test/docs">' in html
    assert '<a href="#cells-parquet">cells.parquet</a>' in html


class _Outline(HTMLParser):
    """Collects what the structure test needs from the page."""

    def __init__(self) -> None:
        super().__init__()
        self.tags: list[tuple[str, dict[str, str | None]]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.tags.append((tag, dict(attrs)))


def test_page_structure(inputs: dict[str, Path]) -> None:
    html = _build(inputs)
    assert html.startswith('<!doctype html>\n<html lang="en-NG">')
    parser = _Outline()
    parser.feed(html)
    tags = parser.tags
    names = [t for t, _ in tags]
    assert "script" not in names
    assert "details" not in names  # the browser's find reaches everything
    body = names.index("body")
    first = tags[body + 1]
    assert first == ("a", {"class": "skip-link", "href": "#main"})
    assert ("main", {"id": "main", "tabindex": "-1", "class": "dictionary-page"}) in tags
    assert names.count("main") == 1 and names.count("footer") == 1 and names.count("h1") == 1
    levels = [int(t[1]) for t in names if re.fullmatch(r"h[1-6]", t)]
    assert levels[0] == 1
    assert all(b - a <= 1 for a, b in itertools.pairwise(levels))
    # Every table: in the scroll wrapper, the caption is the Tab stop, headers are scoped.
    assert html.count("<table>") == html.count(
        '<div class="table-wrap"><table><caption tabindex="0">'
    )
    assert html.count("<table>") == 5  # 3 files, the downloads and the API
    assert all(a.get("scope") in ("col", "row") for t, a in tags if t == "th")
    # Unique anchors; the nav marks this page; the shared footer.
    ids = [a["id"] for _, a in tags if a.get("id")]
    assert len(ids) == len(set(ids))
    assert '<a href="./data-dictionary.html" aria-current="page">Data dictionary</a>' in html
    assert dd.pages.REPORT_HTML in html
    assert '<link rel="stylesheet" href="./src/style.css" />' in html
    assert '<link rel="canonical" href="https://x.test/cc/data-dictionary.html" />' in html


# --- Failures -------------------------------------------------------------------------------


def test_fails_on_a_mart_column_without_a_description(inputs: dict[str, Path], capsys) -> None:
    with duckdb.connect(str(inputs["db"])) as con:
        con.execute("alter table mart_cells add column extra integer")
        target = (inputs["data"] / "cells.parquet").as_posix()
        con.execute(f"copy (select * from mart_cells) to '{target}' (format parquet)")
    with pytest.raises(dd.DictionaryError) as error:
        _build(inputs)
    assert "mart_cells.extra: no description" in str(error.value)
    assert "cells.parquet: extra has no description" in str(error.value)
    argv = ["--db", str(inputs["db"]), "--data-dir", str(inputs["data"])]
    argv += ["--page", str(inputs["tmp"] / "x.html"), "--marts-yml", str(inputs["marts"])]
    assert dd.main([*argv, "--registry", str(inputs["registry"])]) == 1
    assert "Data dictionary failed" in capsys.readouterr().err
    assert not (inputs["tmp"] / "x.html").exists()


def test_fails_on_an_empty_description(inputs: dict[str, Path]) -> None:
    _edit_yaml(inputs["marts"], lambda d: d["models"][1]["columns"][1].pop("description"))
    with pytest.raises(dd.DictionaryError, match=r"mart_results\.value: no description"):
        _build(inputs)


def test_fails_on_a_json_field_without_a_description(inputs: dict[str, Path]) -> None:
    document = {**RESULTS, "added": 3}
    (inputs["data"] / "results.json").write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(dd.DictionaryError, match=r"results\.json: added has no description"):
        _build(inputs)


def test_fails_on_a_stale_mart_description(inputs: dict[str, Path]) -> None:
    _edit_yaml(
        inputs["marts"],
        lambda d: d["models"][0]["columns"].append({"name": "gone", "description": "Old."}),
    )
    with pytest.raises(dd.DictionaryError, match=r"mart_cells\.gone: described, but the mart"):
        _build(inputs)


def test_fails_on_a_stale_field_description(inputs: dict[str, Path]) -> None:
    def change(d: dict[str, Any]) -> None:
        d["files"][2]["fields"]["range.max"] = "Highest."

    _edit_yaml(inputs["registry"], change)
    with pytest.raises(dd.DictionaryError, match=r"describes range\.max, which the file lacks"):
        _build(inputs)


def test_fails_on_jinja_and_on_missing_sources(inputs: dict[str, Path]) -> None:
    def change(d: dict[str, Any]) -> None:
        d["models"][0]["columns"][0]["description"] = "{{ doc('state') }}"
        d["models"][1]["config"]["meta"]["sources"] = []

    _edit_yaml(inputs["marts"], change)
    with pytest.raises(dd.DictionaryError) as error:
        _build(inputs)
    assert "mart_cells.state: Jinja" in str(error.value)
    assert "mart_results: no config.meta.sources" in str(error.value)


def test_fails_when_a_file_or_mart_is_missing(inputs: dict[str, Path]) -> None:
    (inputs["data"] / "results.json").unlink()
    with duckdb.connect(str(inputs["db"])) as con:
        con.execute("drop table mart_results")
    with pytest.raises(dd.DictionaryError) as error:
        _build(inputs)
    assert "results.json: not found" in str(error.value)
    assert "mart_results: not in the warehouse" in str(error.value)


def test_fails_when_the_api_names_an_unknown_file(inputs: dict[str, Path]) -> None:
    _edit_yaml(inputs["registry"], lambda d: d["api"]["endpoints"][0]["files"].append("x.csv"))
    with pytest.raises(dd.DictionaryError, match=r"API /cells: x\.csv is not a public file"):
        _build(inputs)


def test_downloads_description_follows_downloads_py(inputs: dict[str, Path]) -> None:
    fields = dict(dd.load_registry(inputs["registry"]).download_fields)
    assert dd.check_downloads(fields) == []
    missing = {k: v for k, v in fields.items() if k != "terms"}
    assert dd.check_downloads(missing) == ["downloads: terms has no description"]
    extra = {**fields, "licence": dd.Described("Old.")}
    assert dd.check_downloads(extra) == [
        "downloads: public_files.yml describes licence, which downloads.py does not write"
    ]


def test_fails_over_budget(inputs: dict[str, Path], monkeypatch) -> None:
    monkeypatch.setattr(dd, "HTML_BUDGET", 1000)
    with pytest.raises(dd.DictionaryError, match="budget"):
        _build(inputs)


def test_json_paths() -> None:
    found = dd.json_paths([{"a": 1, "b": {"c": None}}, {"a": 2.5, "b": None, "d": []}], {})
    assert dd._type_text(found["[].a"]) == "number"
    assert dd._type_text(found["[].b"]) == "object or null"
    assert dd._type_text(found["[].b.c"]) == "null (in this build)"
    assert found["[].d"] == {"list (empty in this build)"}
    assert "[]" in found and "" not in found


# --- The real YAML and registry -------------------------------------------------------------


@pytest.fixture(scope="module")
def real() -> tuple[dict[str, Any], Any]:
    return dd.load_marts(dd.DEFAULT_MARTS), dd.load_registry(dd.DEFAULT_REGISTRY)


def test_registry_lists_exactly_what_export_marts_writes(real) -> None:
    _, registry = real
    documents = ("states.json", "prevalence.json", "spatial.json", "poverty.json")
    source = (SCRIPTS / "export_marts.py").read_text(encoding="utf-8")
    for name in documents:
        assert f'"{name}": ' in source, name
    expected = {*export.EXPORTS, *export.QUERIES, *documents}
    assert {f.file for f in registry.files} == expected
    by_file = {f.file: f for f in registry.files}
    for name, mart in export.EXPORTS.items():
        assert by_file[name].marts == {"": mart}


def test_every_public_mart_is_fully_described_with_sources(real) -> None:
    marts, registry = real
    names = {m for f in registry.files for m in f.all_marts()}
    assert names, "no marts"
    for name in names:
        mart = marts[name]
        assert mart.sources, name
        assert all(s.get("citation") and s.get("terms") for s in mart.sources), name
        undescribed = [c for c in mart.listed if c not in mart.columns]
        assert undescribed == [], (name, undescribed)
        for column, described in mart.columns.items():
            assert "{{" not in described.description, (name, column)


def test_api_section_matches_the_api(real) -> None:
    _, registry = real
    data = pytest.importorskip("curbcut_api.data")
    status = next(e for e in registry.api["endpoints"] if e["path"] == "/status")
    assert set(status["files"]) == {*data.PARQUET_FILES, *data.JSON_FILES}
    api_doc = (ROOT / "docs" / "api.md").read_text(encoding="utf-8")
    for endpoint in registry.api["endpoints"]:
        assert f"`{endpoint['path']}`" in api_doc, endpoint["path"]


def _nav_links(html: str) -> list[tuple[str, str]]:
    match = re.search(r'<nav class="site-nav" aria-label="Site">(.*?)</nav>', html, re.S)
    assert match, "no site nav"
    return re.findall(r'<a href="([^"]+)"[^>]*>([^<]+)</a>', match.group(1))


def test_site_nav_is_the_same_on_every_page_that_has_one() -> None:
    """index.html and methodology.html repeat the generated nav by hand; keep them in step."""
    expected = _nav_links(dd.nav_html())
    assert ("./data-dictionary.html", "Data dictionary") in expected
    assert _nav_links(poverty_page.nav_html()) == expected
    for name in ("index.html", "methodology.html"):
        assert _nav_links((ROOT / "site" / name).read_text(encoding="utf-8")) == expected, name
    assert 'href="../data-dictionary.html"' in dd.pages.FOOTER_HTML
