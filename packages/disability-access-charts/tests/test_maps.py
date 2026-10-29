"""The experimental choropleth document and its audit."""

import copy
import json
from pathlib import Path
from typing import Any

import pytest
from disability_access_charts import audit, contrast_ratio
from disability_access_charts.cli import main
from disability_access_charts.maps import MAP_THEMES, MapTheme, choropleth, class_labels, classify

NAMES = ["Kano", "Lagos", "Oyo", "Taraba", "Abia"]
CODES = ["NG-KN", "NG-LA", "NG-OY", "NG-TA", "NG-AB"]
VALUES = [4.6, 0.8, 1.996, 11.3, 2.5]
LOWER = [3.6, 0.5, 1.4, 8.9, 1.9]
UPPER = [5.7, 1.2, 2.6, 14.1, 3.2]
PATHS = {code: f"M{i},0 {i + 1},0 {i + 1},1Z" for i, code in enumerate(CODES)}
KW: dict[str, Any] = {
    "paths": PATHS,
    "view_box": "0 0 10 10",
    "breaks": [2, 3, 4, 6],
    "title": "Disability by state (illustrative)",
    "value_label": "Adults with disability (%)",
    "source": "Synthetic",
}


def make(**overrides: Any) -> dict[str, Any]:
    kw = {"lower": LOWER, "upper": UPPER, **KW, **overrides}
    return choropleth(NAMES, CODES, VALUES, **kw)


def failed(doc: dict[str, Any]) -> set[str]:
    return {c["id"] for c in audit(doc)["checks"] if not c["passed"]}


def test_document_shape_and_audit() -> None:
    doc = json.loads(json.dumps(make()))
    assert doc["meta"]["experimental"] is True
    assert doc["meta"]["chart_type"] == "choropleth"
    assert doc["keyboard"]["hover_only_data"] is False
    assert doc["keyboard"]["data_route"] == "table"
    assert set(doc["map"]["paths"]) == set(CODES)
    assert doc["audit"]["passed"] is True
    assert doc["audit"]["warnings"] == 1  # the empty "3% to under 4%" class
    assert audit(doc) == doc["audit"]  # the JSON round trip audits the same


def test_classes_are_fixed_and_classed_as_displayed() -> None:
    assert class_labels([2, 3, 4, 6], "percent") == [
        "Under 2%",
        "2% to under 3%",
        "3% to under 4%",
        "4% to under 6%",
        "6% and over",
    ]
    assert class_labels([2.5, 10], "number") == ["Under 2.5", "2.5 to under 10", "10 and over"]
    # 1.996 is shown as 2.0, so it is in "2% to under 3%", not "Under 2%".
    assert classify(1.996, [2, 3], 1) == 1
    assert classify(1.94, [2, 3], 1) == 0
    assert classify(3.0, [2, 3], 1) == 2
    doc = make()
    assert [r["class"] for r in doc["regions"]] == [3, 0, 1, 4, 1]
    assert [c["count"] for c in doc["classes"]] == [1, 2, 0, 1, 1]
    assert doc["classes"][0]["lower"] is None and doc["classes"][-1]["upper"] is None


def test_alt_text_gives_classes_and_extremes() -> None:
    doc = make()
    text = doc["alt_text"]
    assert text.startswith("Map: Disability by state (illustrative). 5 states, each with its")
    assert doc["alt_text_classes"] in text
    assert "under 2%, 1 state; 2% to under 3%, 2 states; 3% to under 4%, 0 states" in text
    assert "Highest estimate: Taraba, 11.3%" in text
    assert "Lowest estimate: Lagos, 0.8%" in text
    assert text.endswith("Source: Synthetic.")


def test_table_is_sorted_by_name_with_class_and_extra_columns() -> None:
    doc = make(extra_columns=[("Precision", ["ok", "ok", "review", "ok", "ok"])])
    table = doc["table"]
    assert [r[0] for r in table["rows"]] == sorted(NAMES)
    labels = [c["label"] for c in table["columns"]]
    assert labels == [
        "State",
        "Adults with disability (%)",
        "95% confidence interval, lower",
        "95% confidence interval, upper",
        "Map class",
        "Precision",
    ]
    oyo = next(r for r in table["rows"] if r[0] == "Oyo")
    assert oyo[1:] == [1.996, 1.4, 2.6, "2% to under 3%", "review"]


def test_default_themes_meet_the_contrast_rules() -> None:
    for t in MAP_THEMES.values():
        assert contrast_ratio(t.text, t.background) >= 4.5
        assert contrast_ratio(t.edge, t.background) >= 3
        assert all(contrast_ratio(t.edge, fill) >= 3 for fill in t.classes)
    doc = make()
    cue = next(c for c in doc["audit"]["checks"] if c["id"] == "not-colour-alone")
    # The trade-off is reported: neighbouring fills are under 3:1 apart.
    assert all(r < 3 for ratios in cue["adjacent_class_ratios"].values() for r in ratios)
    assert "legend" in cue["note"]


def test_audit_catches_tampering() -> None:
    doc = make()
    bad = copy.deepcopy(doc)
    bad["classes"][0]["count"] = 3
    assert "map-matches-data" in failed(bad)

    bad = copy.deepcopy(doc)
    bad["regions"][1]["class"] = 2
    assert "map-matches-data" in failed(bad)

    bad = copy.deepcopy(doc)
    bad["table"]["rows"][0][1] = 9.9
    assert "map-matches-data" in failed(bad)

    bad = copy.deepcopy(doc)
    del bad["map"]["paths"]["NG-KN"]
    assert "map-matches-data" in failed(bad)

    bad = copy.deepcopy(doc)
    bad["alt_text"] = bad["alt_text"].replace("11.3%", "12.3%")
    assert "alt-text-matches-data" in failed(bad)

    bad = copy.deepcopy(doc)
    wrong = bad["alt_text_classes"].replace("1 state;", "4 states;", 1)
    bad["alt_text"] = bad["alt_text"].replace(bad["alt_text_classes"], wrong)
    bad["alt_text_classes"] = wrong
    assert "alt-text-classes-match-data" in failed(bad)

    bad = copy.deepcopy(doc)
    bad["keyboard"]["hover_only_data"] = True
    assert "keyboard-metadata" in failed(bad)
    assert audit(bad)["passed"] is False


def test_audit_catches_weak_colours() -> None:
    grey = MapTheme("#ffffff", "#1a1a1a", "#bbbbbb", MAP_THEMES["light"].classes)
    doc = make(themes={"light": grey})
    checks = [c for c in doc["audit"]["checks"] if not c["passed"]]
    assert any(c["id"] == "wcag-1.4.11" and "background" in c["description"] for c in checks)
    assert doc["audit"]["passed"] is False

    unordered = MapTheme(
        "#ffffff", "#1a1a1a", "#1a1a1a", tuple(reversed(MAP_THEMES["light"].classes))
    )
    assert "classes-ordered" in failed(make(themes={"light": unordered}))


def test_empty_class_is_a_warning() -> None:
    doc = make()  # "3% to under 4%" is empty
    check = next(c for c in doc["audit"]["checks"] if c["id"] == "class-empty")
    assert check["severity"] == "warning" and not check["passed"]
    assert check["problems"] == ["3% to under 4%"]
    assert doc["audit"]["passed"] is True
    assert doc["audit"]["warnings"] == 1


def test_bad_input_is_refused() -> None:
    with pytest.raises(ValueError, match="no map path"):
        choropleth(NAMES, CODES, VALUES, **{**KW, "paths": {}})
    with pytest.raises(ValueError, match="strictly increasing"):
        make(breaks=[3, 2, 4, 6])
    with pytest.raises(ValueError, match="fills for"):
        make(breaks=[2, 3])
    with pytest.raises(ValueError, match="unique"):
        choropleth(NAMES, ["NG-KN"] * 5, VALUES, **KW)
    with pytest.raises(ValueError, match="at least two"):
        choropleth(["Kano"], ["NG-KN"], [4.6], **KW)
    with pytest.raises(ValueError, match="one entry per region"):
        make(extra_columns=[("Precision", ["ok"])])
    with pytest.raises(ValueError, match="light"):
        make(themes={"dark": MAP_THEMES["dark"]})


def test_cli_checks_map_documents(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    good = tmp_path / "map.json"
    no_empty = choropleth(NAMES, CODES, [4.6, 0.8, 1.996, 11.3, 3.5], lower=None, upper=None, **KW)
    good.write_text(json.dumps(no_empty), encoding="utf-8")
    assert main(["check", "--strict", str(good)]) == 0
    bad = copy.deepcopy(no_empty)
    bad["classes"][0]["count"] = 9
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(bad), encoding="utf-8")
    assert main(["check", str(path)]) == 1
    assert "map-matches-data" in capsys.readouterr().out
