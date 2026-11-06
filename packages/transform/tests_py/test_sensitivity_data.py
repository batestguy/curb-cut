"""Tests for scripts/sensitivity_data.py: the sensitivity page's data and charts (P6 item 11)."""

from __future__ import annotations

import importlib.util
import itertools
import json
import shutil
import sys
from pathlib import Path
from typing import Any

import pytest
from disability_access_charts import audit

ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = ROOT / "packages" / "transform" / "scripts"
FIXTURES = ROOT / "site" / "tests" / "fixtures"


def _load(name: str):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


sd = _load("sensitivity_data")
ex = _load("explorer_charts")


def _fixture_dir(tmp_path: Path) -> Path:
    data = tmp_path / "data"
    data.mkdir()
    for name in (sd.STATE_FILE, sd.COMPARISON_FILE):
        shutil.copy(FIXTURES / name, data / name)
    return data


def _cell(state: str, estimate: float | None = 0.05, **extra: Any) -> dict[str, Any]:
    cell = {
        "state": state,
        "estimate": estimate,
        "ci_low": None if estimate is None else estimate * 0.8,
        "ci_high": None if estimate is None else estimate * 1.2,
        "n_unweighted": None if estimate is None else 500,
        "precision_flag": "reliable",
        "precision_reason": None,
        "suppressed": False,
        "has_data": True,
        "population_2023": 1_000_000,
    }
    cell.update(extra)
    return cell


def test_rates_run_from_2_to_20_in_half_points_with_15_among_them() -> None:
    rates = sd.rates()
    assert rates[0] == 2.0
    assert rates[-1] == 20.0
    assert len(rates) == 37
    assert all(abs(b - a - 0.5) < 1e-12 for a, b in itertools.pairwise(rates))
    assert sd.DEFAULT_RATE in rates
    assert sd.rate_key(15.0) == "15.0"
    assert sd.rate_key(2.5) == "2.5"
    assert sd.chart_name("18+", 15.0) == "18plus-rate-15-0"
    assert sd.chart_name("5-17", 2.5) == "5to17-rate-2-5"


def test_the_definition_sentence_comes_from_the_yaml_and_a_missing_one_fails() -> None:
    text = (
        'What is measured. disability3: the Washington Group Short Set DISABILITY3 measure, "a '
        'lot of difficulty" or "cannot do at all" in at least one of six domains. '
        "<domain>_3plus: one domain alone."
    )
    assert sd.first_sentence_about(text, "disability3") == (
        'The Washington Group Short Set DISABILITY3 measure, "a lot of difficulty" or "cannot '
        'do at all" in at least one of six domains.'
    )
    with pytest.raises(ValueError, match="does not define"):
        sd.first_sentence_about(text, "disability2")


def test_a_chart_draws_the_survey_and_the_assumed_rate_and_leaves_out_cells_without_a_figure() -> (
    None
):
    cells = [
        _cell("Abia", 0.10),
        _cell("Kano", 0.04),
        _cell("Lagos", 0.02),
        _cell("Imo", None, suppressed=True, precision_flag="suppressed"),
        _cell("Oyo", 0.03, precision_flag="unreliable"),
        _cell("Zamfara", None, has_data=False, precision_flag="no_data"),
    ]
    doc, left_out = sd.rate_chart(
        "18+", 15.0, cells, group="Adults 18 and over", missing_text=ex.missing_text
    )
    assert doc is not None
    assert doc["data"]["categories"] == ["Abia", "Kano", "Lagos"]  # highest first
    survey, assumed = doc["data"]["series"]
    assert survey["name"] == sd.SURVEY_SERIES
    assert survey["values"] == pytest.approx([10.0, 4.0, 2.0])
    assert survey["lower"] == pytest.approx([8.0, 3.2, 1.6])
    assert assumed["name"] == sd.ASSUMED_SERIES
    assert assumed["values"] == [15.0, 15.0, 15.0]
    assert assumed.get("lower") is None
    assert {x["place"]: x["why"] for x in left_out} == {
        "Imo": ex.MISSING["too_few"],
        "Oyo": ex.MISSING["unreliable"],
        "Zamfara": ex.MISSING["no_data"],
    }
    assert doc["audit"]["passed"]
    assert doc["audit"]["warnings"] == 0
    assert audit(doc)["passed"]
    # The alt-text is the library's, from the data; it says only the survey has intervals.
    assert "survey estimates only" in doc["alt_text"]
    assert "Assumed rate: all 3 dots are 15.0%." in doc["alt_text"]
    assert "15.0%" in doc["title"]
    assert doc["meta"]["assumed_rate"] == 15.0


def test_a_chart_needs_two_states_with_a_figure() -> None:
    cells = [_cell("Abia"), _cell("Kano", None, has_data=False, precision_flag="no_data")]
    doc, left_out = sd.rate_chart(
        "18+", 15.0, cells, group="Adults 18 and over", missing_text=ex.missing_text
    )
    assert doc is None
    assert [x["place"] for x in left_out] == ["Kano"]


def test_build_writes_the_manifest_and_74_audited_charts(tmp_path: Path) -> None:
    data = _fixture_dir(tmp_path)
    docs = sd.build(data)
    assert len(docs) == 2 * 37
    assert all(doc["audit"]["passed"] for doc in docs.values())
    files = sorted((data / "charts" / sd.CHART_DIR).glob("*.json"))
    assert len(files) == 74
    manifest = json.loads((data / sd.MANIFEST).read_text(encoding="utf-8"))
    assert manifest["rates"] == {"min": 2.0, "max": 20.0, "step": 0.5, "default": 15.0}
    assert [g["value"] for g in manifest["age_groups"]] == ["18+", "5-17"]
    assert manifest["assumption"]["value_percent"] == 15.0
    assert manifest["assumption"]["definition"].startswith("An assumption, not a count")
    assert "not a Washington Group cut-off figure" in manifest["global"]["definition"]
    assert manifest["measure"]["definition"].startswith(
        "The Washington Group Short Set DISABILITY3 measure"
    )
    assert "Not the denominator of the estimate." in manifest["population"]["description"]
    assert manifest["missing"] == ex.MISSING
    # Every state, every age group; the fixture's edge cases are kept as they are.
    for age in ("18+", "5-17"):
        assert len(manifest["states"][age]) == 37
    kids = {c["state"]: c for c in manifest["states"]["5-17"]}
    assert kids["Abia"]["suppressed"] is True
    assert kids["Abia"]["estimate"] is None
    assert kids["Zamfara"]["has_data"] is False
    assert kids["Kano"]["population_2023"] == 15671491
    # One chart entry per age group and rate, with the states left out named.
    assert len(manifest["charts"]) == 74
    entry = manifest["charts"]["5-17|15.0"]
    assert entry["href"] == "charts/sensitivity/5to17-rate-15-0.json"
    assert {x["place"] for x in entry["left_out"]} == {
        "Abia",
        "Adamawa",
        "Anambra",
        "Bauchi",
        "Zamfara",
    }
    assert manifest["dictionary"]["estimate"] == (
        "data-dictionary.html#dhs2024-state-prevalence-parquet--estimate"
    )
    assert manifest["dictionary"]["population_2023"] == (
        "data-dictionary.html#dhs2024-state-prevalence-parquet--population-2023"
    )
    assert manifest["download"]["sources"][0].startswith("The DHS Program")
    assert "Demographic Bulletin 2023" in manifest["download"]["sources"][1]
    # A second build replaces the charts (no stale files).
    (data / "charts" / sd.CHART_DIR / "stale.json").write_text("{}", encoding="utf-8")
    sd.build(data)
    assert not (data / "charts" / sd.CHART_DIR / "stale.json").exists()


def test_the_committed_page_fixture_is_the_build_of_the_fixture_parquet(tmp_path: Path) -> None:
    """site/tests/fixtures/sensitivity.json (used by sensitivity.spec.js) must be what the
    build makes from the committed fixture Parquet files; regenerate it with this build."""
    data = _fixture_dir(tmp_path)
    sd.build(data)
    built = (data / sd.MANIFEST).read_text(encoding="utf-8")
    assert (FIXTURES / sd.MANIFEST).read_text(encoding="utf-8") == built


def test_build_refuses_a_default_that_is_not_jonapwds_rate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data = _fixture_dir(tmp_path)
    monkeypatch.setattr(sd, "DEFAULT_RATE", 14.0)
    with pytest.raises(ValueError, match="not JONAPWD"):
        sd.build(data)


def test_build_refuses_an_unknown_age_group_or_flag(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data = _fixture_dir(tmp_path)
    monkeypatch.setattr(sd, "AGE_GROUPS", (("18+", "Adults 18 and over", "adults 18+"),))
    with pytest.raises(ValueError, match="no label for age group"):
        sd.build(data)
    monkeypatch.undo()

    real = sd.load_cells

    def odd(data_dir: Path) -> dict[str, list[dict[str, Any]]]:
        cells = real(data_dir)
        cells["18+"][0]["precision_flag"] = "odd"
        return cells

    monkeypatch.setattr(sd, "load_cells", odd)
    with pytest.raises(ValueError, match="no label for precision flag"):
        sd.build(data)


def test_load_figures_refuses_a_file_without_the_assumption(tmp_path: Path) -> None:
    import duckdb

    data = tmp_path / "data"
    data.mkdir()
    with duckdb.connect() as con:
        con.execute(
            f"copy (select * from read_parquet('{(FIXTURES / sd.COMPARISON_FILE).as_posix()}') "
            f"where figure_id <> 'jonapwd_2025') to '{(data / sd.COMPARISON_FILE).as_posix()}' "
            "(format parquet)"
        )
    with pytest.raises(ValueError, match="jonapwd_2025"):
        sd.load_figures(data)
