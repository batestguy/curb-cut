"""Tests for scripts/downloads.py (P6 item 2) and the main page's downloads in build_charts.py."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

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


downloads = _load("downloads")
charts_mod = _load("build_charts")

SPEC = {
    "caption": 'Estimates, "quoted", with a comma',
    "columns": [
        {"label": "State", "type": "text"},
        {"label": "Adults (%)", "type": "number", "decimals": 1},
        {"label": "Persons", "type": "integer"},
        {"label": "Share", "type": "percent"},
    ],
    "rows": [
        ["Akwa Ibom, south", 4.5929, 1234567.0, 12.5],
        ["Kano", 0.9298000000000001, 12, 0.03],
    ],
}


def table(**changes):
    base = downloads.from_spec(SPEC, "by-state", "adults by state", downloads.DHS)
    return base if not changes else downloads.TableData(**{**base.__dict__, **changes})


def test_csv_is_plain_and_json_has_the_same_rows_with_provenance() -> None:
    t = table()
    body = downloads.csv_bytes(t)
    text = body.decode("utf-8")
    assert not text.startswith("﻿") and "#" not in text
    rows = downloads.parse_csv(body)
    # Numbers unformatted (no thousands separator, no % sign); binary noise trimmed.
    assert rows == [
        ["State", "Adults (%)", "Persons", "Share (%)"],
        ["Akwa Ibom, south", "4.5929", "1234567", "12.5"],
        ["Kano", "0.9298", "12", "0.03"],
    ]
    document = json.loads(downloads.json_bytes(t, "https://x.test/page.html"))
    assert document["rows"] == [
        ["Akwa Ibom, south", 4.5929, 1234567, 12.5],
        ["Kano", 0.9298, 12, 0.03],
    ]
    assert downloads.same_rows(rows[1:], document["rows"])
    assert document["caption"] == SPEC["caption"]
    assert document["page"] == "https://x.test/page.html"
    assert document["survey"] and document["year"] == "2024" and document["sources"]
    assert document["terms"].startswith("Reuse is subject to the source terms; cite the sources.")
    assert "licen" not in document["terms"].lower()
    assert document["columns"][1] == {
        "label": "Adults (%)",
        "type": "number",
        "decimals": 1,
        "unit": "%",
    }
    assert document["values"] == downloads.VALUES_RULE


@pytest.mark.parametrize(
    ("n", "shown"), [(0, "1 KB"), (400, "1 KB"), (1536, "2 KB"), (5000, "5 KB")]
)
def test_size_text(n: int, shown: str) -> None:
    assert downloads.size_text(n) == shown


def test_the_collector_links_each_file_and_refuses_duplicates(tmp_path: Path) -> None:
    dl = downloads.Collector("https://x.test/p.html", "states/kano", "../data/downloads/")
    line = dl.add(table())
    assert line.startswith('<p class="table-download">Download this table: <a href=')
    assert 'href="../data/downloads/states/kano/by-state.csv" download' in line
    assert 'aria-label="CSV, 1 KB: adults by state">CSV, 1 KB</a> · <a ' in line
    with pytest.raises(ValueError, match="used twice"):
        dl.add(table())
    with pytest.raises(ValueError, match="used twice"):
        dl.add(table(table_id="other"))
    dl.check_linked(line)
    with pytest.raises(ValueError, match="not linked"):
        dl.check_linked("<p>no links</p>")
    (tmp_path / "states" / "kano").mkdir(parents=True)
    (tmp_path / "states" / "kano" / "stale.csv").write_text("x", encoding="utf-8")
    dl.write(tmp_path)
    assert sorted(p.name for p in (tmp_path / "states" / "kano").iterdir()) == [
        "by-state.csv",
        "by-state.json",
    ]


@pytest.mark.parametrize(
    "changes",
    [{"table_id": "By State"}, {"name": ""}, {"name": "x" * 65}, {"rows": (("only one",),)}],
)
def test_bad_tables_are_refused(changes: dict) -> None:
    with pytest.raises(ValueError):
        table(**changes)


def test_main_page_manifest(tmp_path: Path) -> None:
    (tmp_path / "spatial.json").write_text(json.dumps({"moran_table": SPEC}), encoding="utf-8")
    docs = {"prevalence_map": {"table": SPEC}, "prevalence_by_state": {"table": SPEC}}
    path = charts_mod.main_page_downloads(docs, tmp_path, "https://x.test/cc")
    manifest = json.loads(path.read_text(encoding="utf-8"))["tables"]
    assert list(manifest) == ["prevalence-map", "prevalence-by-state", "moran"]
    names = [e["name"] for e in manifest.values()]
    assert len(set(names)) == 3
    for table_id, entry in manifest.items():
        assert [f["href"] for f in entry["files"]] == [
            f"downloads/main/{table_id}.csv",
            f"downloads/main/{table_id}.json",
        ]
        for f in entry["files"]:
            assert (tmp_path / f["href"]).stat().st_size == f["bytes"]
        document = json.loads((tmp_path / entry["files"][1]["href"]).read_text(encoding="utf-8"))
        assert document["page"] == "https://x.test/cc/"
