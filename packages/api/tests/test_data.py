"""Loading and checking the public files (no network: urlopen is replaced)."""

from __future__ import annotations

import io
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import duckdb
import pytest
from curbcut_api import data
from curbcut_api.data import DataError, dir_fetcher, load, slug, store_from_env, url_fetcher


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("Akwa Ibom", "akwa-ibom"),
        ("Federal Capital Territory", "federal-capital-territory"),
        ("Nasarawa", "nasarawa"),
        ("  Cross--River ", "cross-river"),
    ],
)
def test_slug(name: str, expected: str) -> None:
    assert slug(name) == expected


def test_load(data_dir: Path) -> None:
    dataset = load(dir_fetcher(data_dir))
    assert len(dataset.states) == 37
    assert dataset.files["prevalence_comparison.parquet"].rows == 2
    assert dataset.files["poverty.json"].rows == 1
    assert dataset.state_index["ak"] is dataset.state_index["akwa-ibom"]


def _break(data_dir: Path, name: str, content: Any) -> None:
    path = data_dir / name
    if name.endswith(".parquet"):
        with duckdb.connect() as con:
            con.execute("create table t as select unnest(?, recursive := true)", [content])
            con.execute(f"copy t to '{path.as_posix()}' (format parquet)")
    else:
        path.write_text(content if isinstance(content, str) else json.dumps(content), "utf-8")


@pytest.mark.parametrize(
    ("name", "content", "message"),
    [
        ("states.json", "{not json", "not valid JSON"),
        ("states.json", [{"state": "X"}] * 37, "lacks keys"),
        ("states.json", [1] * 37, "non-object"),
        ("poverty.json", [], "must be an object"),
        ("poverty.json", {"note": "x", "estimates": {}}, "lacks keys"),
        ("poverty.json", {"note": "x", "estimates": {}, "summary": {}}, "no estimates"),
        ("prevalence_comparison.parquet", [{"figure_id": "a"}], "lacks columns"),
    ],
)
def test_load_rejects(data_dir: Path, name: str, content: Any, message: str) -> None:
    _break(data_dir, name, content)
    with pytest.raises(DataError, match=message):
        load(dir_fetcher(data_dir))


@pytest.mark.parametrize(
    ("column", "value", "message"),
    [
        ("suppressed", "no", "column suppressed is not all bool"),
        ("has_data", None, "column has_data is not all bool"),
        ("estimate", "0.1", "column estimate is not all num"),
        ("n_unweighted", True, "column n_unweighted is not all num"),
        ("state_code", None, "column state_code is not all str"),
    ],
)
def test_load_rejects_wrong_types(
    data_dir: Path, fx: SimpleNamespace, column: str, value: Any, message: str
) -> None:
    rows = [r | {column: value} for r in fx.state_cells()]
    _break(data_dir, "dhs2024_state_prevalence.parquet", rows)
    with pytest.raises(DataError, match=message):
        load(dir_fetcher(data_dir))


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("state", 1, "must be text"),
        ("dhs2024", [0.1], "object or null"),
    ],
)
def test_load_rejects_wrong_state_types(
    data_dir: Path, field: str, value: Any, message: str
) -> None:
    states = json.loads((data_dir / "states.json").read_text("utf-8"))
    states[3][field] = value
    _break(data_dir, "states.json", states)
    with pytest.raises(DataError, match=message):
        load(dir_fetcher(data_dir))


def test_error_detail_stays_out_of_the_message(data_dir: Path) -> None:
    (data_dir / "prevalence_comparison.parquet").write_bytes(b"not parquet")
    with pytest.raises(DataError) as caught:
        load(dir_fetcher(data_dir))
    assert (
        str(caught.value) == "prevalence_comparison.parquet failed validation: not readable Parquet"
    )
    assert caught.value.detail  # DuckDB's own text, kept for the log


def test_load_rejects_duplicate_codes(data_dir: Path) -> None:
    states = json.loads((data_dir / "states.json").read_text("utf-8"))
    states[1]["state_code"] = states[0]["state_code"]
    _break(data_dir, "states.json", states)
    with pytest.raises(DataError, match="not unique"):
        load(dir_fetcher(data_dir))


def test_load_rejects_missing_states_in_cells(data_dir: Path, fx: SimpleNamespace) -> None:
    _break(data_dir, "dhs2024_state_prevalence.parquet", fx.state_cells()[:8])
    with pytest.raises(DataError, match="cover 37 states"):
        load(dir_fetcher(data_dir))


def test_load_rejects_no_national(data_dir: Path, fx: SimpleNamespace) -> None:
    rows = [r for r in fx.national_zone_cells() if r["geography_level"] == "zone"]
    _break(data_dir, "dhs2024_national_zone.parquet", rows)
    with pytest.raises(DataError, match="no national"):
        load(dir_fetcher(data_dir))


def test_load_rejects_unreadable_parquet(data_dir: Path) -> None:
    (data_dir / "dhs2024_national_zone.parquet").write_bytes(b"not parquet")
    with pytest.raises(DataError, match="not readable Parquet"):
        load(dir_fetcher(data_dir))


def test_load_rejects_empty_parquet(data_dir: Path) -> None:
    path = (data_dir / "prevalence_comparison.parquet").as_posix()
    with duckdb.connect() as con:
        con.execute(
            f"copy (select * from read_parquet('{path}') where false) "
            f"to '{path}.tmp' (format parquet)"
        )
    Path(path + ".tmp").replace(path)
    with pytest.raises(DataError, match="has no rows"):
        load(dir_fetcher(data_dir))


def test_load_rejects_missing_file(data_dir: Path) -> None:
    (data_dir / "poverty.json").unlink()
    with pytest.raises(DataError, match=r"could not fetch poverty\.json"):
        load(dir_fetcher(data_dir))


class _Response(io.BytesIO):
    def __enter__(self) -> _Response:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()


def test_url_fetcher(monkeypatch: pytest.MonkeyPatch, data_dir: Path) -> None:
    seen: list[str] = []

    def fake_urlopen(request: Any, timeout: float) -> _Response:
        seen.append(request.full_url)
        assert timeout == data.TIMEOUT_S
        return _Response((data_dir / request.full_url.rsplit("/", 1)[1]).read_bytes())

    monkeypatch.setattr(data.urllib.request, "urlopen", fake_urlopen)
    dataset = load(url_fetcher("https://example.invalid/data"))
    assert len(dataset.states) == 37
    assert seen[0] == "https://example.invalid/data/dhs2024_state_prevalence.parquet"


def test_url_fetcher_refuses_large(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(data, "MAX_BYTES", 10)
    monkeypatch.setattr(
        data.urllib.request, "urlopen", lambda request, timeout: _Response(b"x" * 11)
    )
    with pytest.raises(DataError, match="larger than 10 bytes"):
        url_fetcher("https://example.invalid/")("states.json")


def test_store_from_env(data_dir: Path) -> None:
    local = store_from_env({"CURBCUT_DATA_DIR": str(data_dir)})
    assert local.source == "local directory"
    assert local.ensure() is not None
    assert store_from_env({}).source == data.DEFAULT_BASE
    assert store_from_env({"CURBCUT_DATA_BASE": "https://x.invalid/d/"}).source == (
        "https://x.invalid/d/"
    )
