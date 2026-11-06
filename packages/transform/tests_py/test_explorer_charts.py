"""Tests for scripts/explorer_charts.py: the data explorer's labels, charts and manifest (P6)."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import duckdb
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


ex = _load("explorer_charts")
pages = _load("build_state_pages")
DOMAINS = dict(pages.DOMAINS)
DOMAIN_CODES = [code for code, _ in pages.DOMAINS]
STATES = ["Abia", "Kano", "Lagos", "Zamfara"]
ZONES = ["North West", "South East", "South West"]


def _cell(place: str, estimate: float | None = 0.05, **extra: Any) -> dict[str, Any]:
    cell = {
        "place": place,
        "estimate": estimate,
        "ci_low": None if estimate is None else estimate * 0.8,
        "ci_high": None if estimate is None else estimate * 1.2,
        "n_unweighted": None if estimate is None else 500,
        "precision_flag": "reliable",
        "precision_reason": None,
        "suppressed": False,
        "has_data": True,
    }
    cell.update(extra)
    return cell


def test_measure_labels_come_from_the_yaml_words_and_unknown_codes_fail() -> None:
    assert ex.measure_label("disability3", DOMAINS) == ex.DISABILITY3_LABEL
    assert ex.measure_label("seeing_3plus", DOMAINS) == (
        "Seeing: a lot of difficulty or cannot do at all"
    )
    assert (
        ex.measure_label("cognition_level_1", DOMAINS)
        == "Remembering or concentrating: no difficulty"
    )
    assert ex.measure_label("selfcare_level_4", DOMAINS) == "Self-care: cannot do at all"
    for bad in ("happiness", "seeing_level_5", "flying_3plus", "mpi_selfcare_3plus"):
        with pytest.raises(ValueError, match="no label"):
            ex.measure_label(bad, DOMAINS)


def test_measures_are_ordered_headline_activities_then_levels() -> None:
    measures = ["walking_level_2", "seeing_3plus", "disability3", "seeing_level_1", "walking_3plus"]
    ordered = sorted(measures, key=lambda m: ex.measure_order(m, DOMAIN_CODES))
    assert ordered == [
        "disability3",
        "seeing_3plus",
        "walking_3plus",
        "seeing_level_1",
        "walking_level_2",
    ]


def test_cells_without_a_figure_get_words_never_numbers() -> None:
    assert ex.missing_text(_cell("A")) is None
    assert ex.missing_text(_cell("A", None, has_data=False)) == "No data"
    too_few = _cell("A", None, suppressed=True, precision_reason="n<30 (disclosure)")
    assert ex.missing_text(too_few) == "Suppressed (fewer than 30 respondents)"
    withheld = _cell(
        "A", None, suppressed=True, precision_reason="complementary suppression (disclosure)"
    )
    assert ex.missing_text(withheld) == ex.MISSING["withheld"]
    assert ex.missing_text(_cell("A", precision_flag="unreliable")) == ex.MISSING["unreliable"]


def test_chart_names_and_view_keys() -> None:
    assert ex.chart_name("state", "seeing_3plus", "5-17", "female") == (
        "state-seeing-3plus-5to17-female"
    )
    assert ex.chart_name("zone", "disability3", "18+", "all") == "zone-disability3-18plus-all"
    assert ex.view_key("state", "disability3", "18+", "all") == "state|disability3|18+|all"
    assert ex.group_label("5-17", "female", pages.GROUPS) == "Girls 5–17"  # noqa: RUF001
    with pytest.raises(ValueError):
        ex.group_label("0-4", "all", pages.GROUPS)


def test_a_chart_draws_exactly_the_rows_with_a_figure_highest_first() -> None:
    cells = [
        _cell("Lagos", 0.02),
        _cell("Kano", 0.06, precision_flag="review", precision_reason="low_events<10"),
        _cell("Abia", None, suppressed=True, precision_reason="n<30 (disclosure)"),
        _cell("Taraba", 0.03, precision_flag="unreliable"),
        _cell("Zamfara", None, has_data=False),
        _cell("Benue", 0.0, precision_flag="review", precision_reason="zero_events"),
    ]
    doc, left_out = ex.view_chart(
        "state", "disability3", "18+", "all", cells, label="Disability", group="Adults 18+"
    )
    assert doc is not None
    assert doc["audit"]["passed"], doc["audit"]
    assert doc["data"]["categories"] == ["Kano", "Lagos", "Benue"]
    series = doc["data"]["series"][0]
    assert series["values"] == pytest.approx([6.0, 2.0, 0.0])
    assert doc["meta"]["places"] == "states"
    assert doc["title"] == "Disability. Adults 18+, by state, with 95% confidence intervals"
    assert [item["place"] for item in left_out] == ["Abia", "Taraba", "Zamfara"]
    assert left_out[1]["why"] == ex.MISSING["unreliable"]


def test_fewer_than_two_places_with_a_figure_means_no_chart() -> None:
    doc, left_out = ex.view_chart(
        "zone",
        "disability3",
        "5-17",
        "all",
        [_cell("South East", None, suppressed=True), _cell("North West", 0.02)],
        label="Disability",
        group="Children 5–17",  # noqa: RUF001
    )
    assert doc is None
    assert left_out == [{"place": "South East", "why": ex.MISSING["too_few"]}]


def _write_files(data_dir: Path, *, extra_measure: str | None = None) -> None:
    """Small Parquet files with the export's columns (only those the explorer reads)."""
    data_dir.mkdir(parents=True, exist_ok=True)
    state_rows = []
    zone_rows = []
    measures = ["disability3", "seeing_3plus", *([extra_measure] if extra_measure else [])]
    for measure in measures:
        for age in ("18+", "5-17"):
            for sex in ("all", "female", "male"):
                for i, state in enumerate(STATES):
                    no_data = state == "Zamfara"
                    suppressed = state == "Abia" and age == "5-17"
                    est = None if no_data or suppressed else 0.01 * (i + 1)
                    state_rows.append(
                        (
                            state,
                            measure,
                            age,
                            sex,
                            est,
                            None if est is None else est / 2,
                            None if est is None else est * 2,
                            None if est is None else 400 + i,
                            "no_data" if no_data else "suppressed" if suppressed else "reliable",
                            "n<30 (disclosure)" if suppressed else None,
                            suppressed,
                            not no_data,
                        )
                    )
                for j, zone in enumerate(ZONES):
                    est = 0.02 * (j + 1)
                    zone_rows.append(
                        ("zone", zone, measure, age, sex, est, est / 2, est * 2, 900, "reliable")
                    )
                zone_rows.append(
                    ("national", "NG", measure, age, sex, 0.03, 0.02, 0.04, 9000, "reliable")
                )
    zone_rows.append(
        ("national", "NG", "seeing_level_1", "18+", "all", 0.9, 0.89, 0.91, 9000, "reliable")
    )
    with duckdb.connect() as con:
        con.execute(
            "create table s (state varchar, measure varchar, age_group varchar, sex varchar, "
            "estimate double, ci_low double, ci_high double, n_unweighted integer, "
            "precision_flag varchar, precision_reason varchar, suppressed boolean, "
            "has_data boolean)"
        )
        con.executemany("insert into s values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", state_rows)
        con.execute(
            "create table z (geography_level varchar, geography varchar, measure varchar, "
            "age_group varchar, sex varchar, estimate double, ci_low double, ci_high double, "
            "n_unweighted integer, precision_flag varchar)"
        )
        con.executemany("insert into z values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", zone_rows)
        con.execute(
            "copy (select * from s) to ? (format parquet)",
            [(data_dir / ex.STATE_FILE).as_posix()],
        )
        con.execute(
            "copy (select *, cast(null as varchar) as precision_reason, false as suppressed "
            "from z) to ? (format parquet)",
            [(data_dir / ex.NATIONAL_ZONE_FILE).as_posix()],
        )


def test_build_writes_a_chart_per_view_and_the_manifest(tmp_path: Path) -> None:
    _write_files(tmp_path)
    stale = tmp_path / "charts" / ex.CHART_DIR / "stale.json"
    stale.parent.mkdir(parents=True)
    stale.write_text("{}", encoding="utf-8")
    docs = ex.build(tmp_path)
    assert not stale.exists()
    # 2 measures x 2 ages x 3 sexes, for states and for zones; none for Nigeria.
    assert len(docs) == 24
    assert all(d["audit"]["passed"] for d in docs.values())
    written = sorted(p.stem for p in (tmp_path / "charts" / ex.CHART_DIR).iterdir())
    assert written == sorted(name.split("/")[1] for name in docs)

    manifest = json.loads((tmp_path / ex.MANIFEST).read_text(encoding="utf-8"))
    assert [m["value"] for m in manifest["measures"]] == [
        "disability3",
        "seeing_3plus",
        "seeing_level_1",
    ]
    assert manifest["files"] == {
        "state": ex.STATE_FILE,
        "zone": ex.NATIONAL_ZONE_FILE,
        "national": ex.NATIONAL_ZONE_FILE,
    }
    entry = manifest["charts"]["state|disability3|5-17|all"]
    assert entry["href"] == "charts/explorer/state-disability3-5to17-all.json"
    assert [e["place"] for e in entry["left_out"]] == ["Abia", "Zamfara"]
    assert "national|disability3|18+|all" not in manifest["charts"]
    assert manifest["dictionary"]["zone"]["precision_flag"] == (
        "data-dictionary.html#dhs2024-national-zone-parquet--precision-flag"
    )
    assert manifest["dictionary"]["state"]["n_unweighted"] == (
        "data-dictionary.html#dhs2024-state-prevalence-parquet--n-unweighted"
    )
    download = manifest["download"]
    downloads = _load("downloads")
    assert download["terms"] == downloads.DHS.terms
    assert download["values"] == downloads.VALUES_RULE
    assert manifest["groups"]["18+|female"] == "Women 18+"
    assert manifest["flags"]["review"] == pages.FLAG_TEXT["review"]
    assert manifest["places"]["national"] == {"value": "NG", "label": "Nigeria"}


def test_build_refuses_a_code_it_cannot_label(tmp_path: Path) -> None:
    _write_files(tmp_path, extra_measure="happiness_3plus")
    with pytest.raises(ValueError, match="no label for measure"):
        ex.build(tmp_path)


def _replace(tmp_path: Path, column: str, value: str) -> None:
    """Set one column of the state file to ``value`` in every row."""
    src = (tmp_path / ex.STATE_FILE).as_posix()
    out = tmp_path / "x.parquet"
    with duckdb.connect() as con:
        con.execute(
            f"copy (select * replace ('{value}' as {column}) from read_parquet('{src}')) "
            f"to '{out.as_posix()}' (format parquet)"
        )
    out.replace(tmp_path / ex.STATE_FILE)


def test_build_refuses_an_unknown_precision_flag(tmp_path: Path) -> None:
    _write_files(tmp_path)
    _replace(tmp_path, "precision_flag", "maybe")
    with pytest.raises(ValueError, match="no label for precision flag"):
        ex.build(tmp_path)


def test_build_refuses_an_unknown_sex(tmp_path: Path) -> None:
    _write_files(tmp_path)
    _replace(tmp_path, "sex", "other")
    with pytest.raises(ValueError, match="no label for sex"):
        ex.build(tmp_path)
