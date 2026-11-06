"""The choropleth document (stable since 0.2) and its audit."""

import copy
import json
from pathlib import Path
from typing import Any

import pytest
from disability_access_charts import audit, contrast_ratio
from disability_access_charts.cli import main
from disability_access_charts.maps import (
    MAP_SCHEMES,
    MAP_THEMES,
    MapTheme,
    choropleth,
    class_labels,
    classify,
)
from disability_access_charts.vision import CVD_MIN_DELTA_E, CVD_TARGET_DELTA_E, delta_e

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
    assert doc["meta"]["experimental"] is False  # stable since 0.2
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
    assert MAP_THEMES is MAP_SCHEMES["ylgnbu"]  # the default since 0.3
    assert MAP_THEMES["light"].classes == ("#ffffcc", "#a1dab4", "#41b6c4", "#2c7fb8", "#253494")
    for t in MAP_THEMES.values():
        assert t.halo is not None
        assert contrast_ratio(t.text, t.background) >= 4.5
        assert contrast_ratio(t.edge, t.background) >= 3
        assert contrast_ratio(t.edge, t.halo) >= 3
        # Cased: for the background and every fill, the edge or the halo is 3:1.
        for colour in (t.background, *t.classes):
            assert max(contrast_ratio(t.edge, colour), contrast_ratio(t.halo, colour)) >= 3
    # The 0.2 greens keep one boundary colour, 3:1 against every fill.
    for t in MAP_SCHEMES["green"].values():
        assert t.halo is None
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


def _checks(doc: dict[str, Any], check_id: str, theme: str = "light") -> list[dict[str, Any]]:
    return [c for c in audit(doc)["checks"] if c["id"] == check_id and c.get("theme") == theme]


def test_cased_boundaries_are_audited_against_every_fill() -> None:
    doc = make()
    for theme in ("light", "dark"):
        cased = [
            c
            for c in _checks(doc, "wcag-1.4.11", theme)
            if c["description"].startswith("State boundaries (edge or halo)")
        ]
        assert len(cased) == 6  # the background and the five fills
        assert all(c["passed"] and "edge_ratio" in c and "halo_ratio" in c for c in cased)
    # In the light theme the white halo carries the darkest fill, the edge the others.
    darkest = next(c for c in _checks(doc, "wcag-1.4.11") if c["background"] == "#253494")
    assert darkest["edge_ratio"] < 3 <= darkest["halo_ratio"]
    assert doc["themes"]["light"]["halo"] == "#ffffff"


def test_casing_widths_are_in_the_document() -> None:
    doc = make()
    assert doc["map"]["casing"] == {
        "halo": 3,
        "edge": 1,
        "active_halo": 5,
        "active_edge": 2,
        "outline_halo": 6,
        "outline_edge": 3,
    }
    check = next(c for c in doc["audit"]["checks"] if c["id"] == "casing-widths")
    assert check["passed"] is True
    # One edge colour, no casing: no widths and no check.
    green = make(scheme="green")
    assert "casing" not in green["map"]
    assert not any(c["id"] == "casing-widths" for c in green["audit"]["checks"])
    # A halo no wider than its edge would be hidden under it.
    bad = copy.deepcopy(doc)
    bad["map"]["casing"]["active_halo"] = 2
    assert "casing-widths" in failed(bad)
    bad = copy.deepcopy(doc)
    del bad["map"]["casing"]
    assert "casing-widths" in failed(bad)


def test_a_single_edge_fails_on_ylgnbu() -> None:
    # No one boundary colour is 3:1 against both #ffffcc and #253494: without the halo the
    # near-black edge is 1.54:1 on the darkest fill.
    light = MAP_THEMES["light"]
    single = MapTheme(light.background, light.text, light.edge, light.classes)
    doc = make(themes={"light": single})
    low = [c for c in _checks(doc, "wcag-1.4.11") if not c["passed"]]
    assert [c["background"] for c in low] == ["#253494"]
    assert doc["audit"]["passed"] is False
    # A halo that does not stand out from the edge fails too, and so does one that leaves a
    # fill with neither the edge nor the halo at 3:1.
    weak = MapTheme(light.background, light.text, light.edge, light.classes, halo="#333333")
    failed_checks = [
        c for c in _checks(make(themes={"light": weak}), "wcag-1.4.11") if not c["passed"]
    ]
    assert any(c["description"] == "Boundary edge against its halo" for c in failed_checks)
    assert any(c["background"] == "#253494" for c in failed_checks)


def test_fills_in_the_wrong_order_fail() -> None:
    for name in ("light", "dark"):
        t = MAP_THEMES[name]
        wrong = MapTheme(t.background, t.text, t.edge, tuple(reversed(t.classes)), halo=t.halo)
        assert "classes-ordered" in failed(make(themes={"light": MAP_THEMES["light"], name: wrong}))
    # Dark mode: brighter for higher values.
    assert "classes-ordered" not in failed(make())


def test_colour_vision_check_reports_the_minimum_difference() -> None:
    doc = make()
    for theme, low, vision in (("light", 10.3, "protanopia"), ("dark", 11.6, "deuteranopia")):
        (check,) = _checks(doc, "colour-vision", theme)
        assert check["passed"] and check["min_delta_e"] == low
        assert check["worst_vision"] == vision
        assert set(check["min_delta_e_by_vision"]) == {
            "normal",
            "deuteranopia",
            "protanopia",
            "tritanopia",
        }
        assert check["minimum"] == CVD_MIN_DELTA_E
        (target,) = _checks(doc, "colour-vision-target", theme)
        assert target["passed"] and target["minimum"] == CVD_TARGET_DELTA_E
    # The 0.2 greens pass the floor but miss the target: a warning, not an error.
    green = make(scheme="green")
    assert green["audit"]["passed"] is True
    targets = [c for c in green["audit"]["checks"] if c["id"] == "colour-vision-target"]
    assert [c["min_delta_e"] for c in targets] == [7.5, 8.2]
    assert not any(c["passed"] for c in targets)


def test_fills_that_merge_for_colour_blind_readers_fail() -> None:
    # Classes 2 and 3 differ clearly in normal vision but almost vanish under deuteranopia.
    a, b = "#78a578", "#c37878"
    assert delta_e(a, b) > 40 and delta_e(a, b, "deuteranopia") < CVD_MIN_DELTA_E
    light = MAP_THEMES["light"]
    fills = (light.classes[0], a, b, light.classes[3], light.classes[4])
    theme = MapTheme(light.background, light.text, light.edge, fills, halo=light.halo)
    doc = make(themes={"light": theme})
    (check,) = _checks(doc, "colour-vision", "light")
    assert check["passed"] is False and check["worst_vision"] == "deuteranopia"
    assert "classes-ordered" not in failed(doc)  # only the colour-vision rule catches it
    assert doc["audit"]["passed"] is False


def test_green_scheme_is_the_02_look() -> None:
    doc = make(scheme="green")
    assert doc["meta"]["scheme"] == "green"
    assert doc["themes"] == {
        "light": {
            "background": "#ffffff",
            "text": "#1a1a1a",
            "edge": "#1a1a1a",
            "classes": ("#e4f3e9", "#b5dec3", "#7dc39a", "#3fa16f", "#008751"),
        },
        "dark": {
            "background": "#121212",
            "text": "#f0f0f0",
            "edge": "#ffffff",
            "classes": ("#1b2f23", "#1e4b33", "#226943", "#2a8753", "#34a061"),
        },
    }
    assert make()["meta"]["scheme"] == "ylgnbu"
    assert make(themes=MAP_SCHEMES["green"])["meta"]["scheme"] == "custom"
    assert make()["meta"]["schema"] == "1.2"
    with pytest.raises(ValueError, match="unknown map scheme"):
        make(scheme="viridis")


def test_legend_filter_metadata() -> None:
    doc = make()
    assert doc["keyboard"]["legend_filter"] is True
    assert [c["regions"] for c in doc["classes"]] == [
        ["Lagos"],
        ["Abia", "Oyo"],
        [],
        ["Kano"],
        ["Taraba"],
    ]
    assert [c["announce"] for c in doc["classes"]] == [
        "Showing 1 state in under 2%: Lagos.",
        "Showing 2 states in 2% to under 3%: Abia, Oyo.",
        "No states are in 3% to under 4%.",
        "Showing 1 state in 4% to under 6%: Kano.",
        "Showing 1 state in 6% and over: Taraba.",
    ]
    assert doc["legend"]["announce_all"] == "Showing all 5 states."
    assert doc["legend"]["templates"]["filter_class"] == "Showing {n} {noun} in {range}: {names}."
    check = next(c for c in doc["audit"]["checks"] if c["id"] == "legend-filter-matches-data")
    assert check["passed"] is True

    for tamper in (
        lambda d: d["classes"][1]["regions"].append("Kano"),
        lambda d: d["classes"][3].__setitem__(
            "announce", "Showing 1 state in 4% to under 6%: Oyo."
        ),
        lambda d: d["legend"].__setitem__("announce_all", "Showing all 6 states."),
    ):
        bad = copy.deepcopy(doc)
        tamper(bad)
        assert "legend-filter-matches-data" in failed(bad)

    off = make(legend_filter=False)
    assert "legend" not in off and off["keyboard"]["legend_filter"] is False
    assert all("announce" not in c for c in off["classes"])
    assert not any(c["id"] == "legend-filter-matches-data" for c in off["audit"]["checks"])


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
