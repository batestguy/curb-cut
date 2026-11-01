"""Pattern tiles: the designs, the ink rule, bars, grouped bars, maps, and their audit checks."""

import copy
import itertools
import re
from typing import Any

import pytest
from disability_access_charts import (
    DEFAULT_THEMES,
    MAP_SCHEMES,
    MAP_THEMES,
    PATTERNS,
    MapTheme,
    Series,
    Theme,
    audit,
    bar,
    choropleth,
    contrast_ratio,
    grouped_bar,
    theme,
)
from disability_access_charts.patterns import (
    BLACK,
    MAP_PATTERNS,
    MAP_SEQUENCES,
    WHITE,
    assign,
    assign_map,
    best_ink,
    class_inks,
    get,
    has_ink,
    ink_for,
    plotly_pattern,
    svg_pattern,
)

KW: dict[str, Any] = {
    "title": "Synthetic",
    "value_label": "Prevalence (%)",
    "category_label": "State",
    "source": "Synthetic",
}
WOMEN = Series("Women", (6.0, 1.0, 2.0), (5.0, 0.5, 1.5), (7.0, 1.5, 2.5))
MEN = Series("Men", (3.0, 0.9, 2.1), (2.5, 0.5, 1.6), (3.5, 1.3, 2.6))
STATES = ["Kano", "Lagos", "Oyo"]

NAMES = ["Kano", "Lagos", "Oyo", "Taraba", "Abia"]
CODES = ["NG-KN", "NG-LA", "NG-OY", "NG-TA", "NG-AB"]
MAP_KW: dict[str, Any] = {
    "paths": {code: f"M{i},0 {i + 1},0 {i + 1},1Z" for i, code in enumerate(CODES)},
    "view_box": "0 0 632 520",
    "breaks": [2, 3, 4, 6],
    "title": "Disability by state (illustrative)",
    "value_label": "Adults with disability (%)",
    "source": "Synthetic",
}
MAP_VALUES = [4.6, 0.8, 2.5, 11.3, 3.5]
_LIGHT = MAP_THEMES["light"]
THREE = {
    "light": MapTheme(
        _LIGHT.background, _LIGHT.text, _LIGHT.edge, _LIGHT.classes[::2], halo=_LIGHT.halo
    )
}
# ColorBrewer's six-class YlGnBu, with the default casing.
SIX = {
    "light": MapTheme(
        _LIGHT.background,
        _LIGHT.text,
        _LIGHT.edge,
        ("#ffffcc", "#c7e9b4", "#7fcdbb", "#41b6c4", "#2c7fb8", "#253494"),
        halo=_LIGHT.halo,
    )
}


def failed(doc: dict[str, Any]) -> set[str]:
    return {c["id"] for c in audit(doc)["checks"] if not c["passed"]}


def test_five_distinct_tiles_inside_their_square() -> None:
    assert [p.id for p in PATTERNS] == ["dots", "rings", "checks", "lines", "crosshatch"]
    assert len({p.path for p in PATTERNS}) == 5
    for p in PATTERNS:
        numbers = [float(x) for x in re.findall(r"-?\d+(?:\.\d+)?", p.path)]
        assert numbers and p.size == 12
        assert p.inspiration  # every design records what it is after
    # Absolute coordinates stay in the tile (arc radii and relative moves are small).
    for p in (get("checks"), get("lines"), get("crosshatch")):
        coords = [float(x) for x in re.findall(r"\d+(?:\.\d+)?", p.path)]
        assert all(0 <= c <= 12 for c in coords)
    with pytest.raises(ValueError, match="unknown pattern"):
        get("nsibidi")
    with pytest.raises(ValueError, match="at most 5"):
        assign(6)


def test_ink_is_black_or_white_with_the_higher_lowest_contrast() -> None:
    green = MAP_SCHEMES["green"]
    assert ink_for(green["light"].classes) == BLACK
    assert ink_for(green["dark"].classes) == WHITE
    for name, t in green.items():
        ink = ink_for(t.classes)
        assert all(contrast_ratio(ink, c) >= 3 for c in t.classes), name
    # The 0.3 scheme runs from light to dark fills, so no one ink suits every class: each
    # class gets its own, the better of black and white for its fill.
    for name, t in MAP_THEMES.items():
        inks = class_inks(MAP_PATTERNS, t.classes)
        assert inks[0] is None and inks[-1] is None  # plain and solid draw no ink
        for ink, fill in zip(inks[1:-1], t.classes[1:-1], strict=True):
            assert ink == best_ink(fill)
            assert ink is not None and contrast_ratio(ink, fill) >= 3, name
    light = class_inks(MAP_PATTERNS, MAP_THEMES["light"].classes)
    assert light == [None, BLACK, BLACK, BLACK, None]
    dark = class_inks(MAP_PATTERNS, MAP_THEMES["dark"].classes)
    assert dark == [None, WHITE, BLACK, BLACK, None]
    for t in DEFAULT_THEMES.values():
        ink = ink_for(t.series)
        assert all(contrast_ratio(ink, c) >= 3 for c in t.series)
        assert contrast_ratio(ink_for([t.mark]), t.mark) >= 3


def test_renderers() -> None:
    tile = get("rings")
    spec = plotly_pattern(tile, ink="#000000", fill="#0072b2")
    assert spec == {
        "path": tile.path,
        "size": 12,
        "fgcolor": "#000000",
        "bgcolor": "#0072b2",
        "fgopacity": 1,
        "fillmode": "overlay",
    }
    svg = svg_pattern(tile, pattern_id='m"x', ink="#fff", fill="#123456", scale=0.5)
    assert svg.startswith('<pattern id="m&quot;x" patternUnits="userSpaceOnUse"')
    assert 'patternTransform="scale(0.5)"' in svg and 'fill="#123456"' in svg


def test_bar_patterns_are_off_by_default_so_01_documents_are_unchanged() -> None:
    doc = bar(["Kano", "Lagos"], [3, 4], **KW)
    assert "patterns" not in doc and "findings" not in doc
    assert "pattern" not in doc["plotly"]["data"][0]["marker"]
    assert set(doc) == {
        "id",
        "title",
        "plotly",
        "themes",
        "alt_text",
        "table",
        "data",
        "keyboard",
        "meta",
        "audit",
    }
    on = bar(["Kano", "Lagos"], [3, 4], patterns=True, **KW)
    assert on["patterns"]["series"] == ["dots"]
    assert on["plotly"]["data"][0]["marker"]["pattern"]["path"] == get("dots").path
    assert on["audit"]["passed"] is True


def test_grouped_bars_have_one_pattern_and_colour_per_series_and_a_legend() -> None:
    doc = grouped_bar(STATES, [WOMEN, MEN], **KW)
    traces = doc["plotly"]["data"]
    assert [t["marker"]["pattern"]["path"] for t in traces] == [get("dots").path, get("rings").path]
    light = DEFAULT_THEMES["light"]
    assert [t["marker"]["color"] for t in traces] == list(light.series[:2])
    assert [t["marker"]["pattern"]["bgcolor"] for t in traces] == list(light.series[:2])
    assert doc["plotly"]["layout"]["showlegend"] is True
    assert doc["plotly"]["layout"]["barmode"] == "group"
    assert doc["alt_text"].startswith("Bar chart: Synthetic. 3 rows, one per state, with 2 series")
    ids = {c["id"] for c in doc["audit"]["checks"]}
    assert {"patterns-one-to-one", "patterns-ink-contrast", "patterns-legend"} <= ids
    assert doc["audit"]["passed"] is True and doc["audit"]["warnings"] == 0
    with pytest.raises(ValueError, match="at least two series"):
        grouped_bar(STATES, [WOMEN], **KW)


def test_grouped_bars_without_patterns_warn() -> None:
    doc = grouped_bar(STATES, [WOMEN, MEN], patterns=False, **KW)
    cue = next(c for c in doc["audit"]["checks"] if c["id"] == "not-colour-alone")
    assert cue["severity"] == "warning" and not cue["passed"]
    assert doc["audit"]["passed"] is True


def test_theming_switches_colours_and_ink() -> None:
    doc = grouped_bar(STATES, [WOMEN, MEN], **KW)
    dark = theme(doc, "dark")
    traces = dark["plotly"]["data"]
    want = DEFAULT_THEMES["dark"].series[:2]
    assert [t["marker"]["color"] for t in traces] == list(want)
    assert [t["marker"]["pattern"]["bgcolor"] for t in traces] == list(want)
    assert {t["marker"]["pattern"]["fgcolor"] for t in traces} == {doc["patterns"]["ink"]["dark"]}


def test_plotly_accepts_the_patterns() -> None:
    pytest.importorskip("plotly")
    from disability_access_charts import figure

    fig = figure(grouped_bar(STATES, [WOMEN, MEN], **KW), "dark")
    assert fig.data[0].marker.pattern.path == get("dots").path


# --- Break tests: each new pattern check fails when it should -------------------------------


def test_audit_catches_a_shared_pattern() -> None:
    doc = grouped_bar(STATES, [WOMEN, MEN], **KW)
    bad = copy.deepcopy(doc)
    bad["patterns"]["series"][1] = "dots"
    bad["plotly"]["data"][1]["marker"]["pattern"]["path"] = get("dots").path
    assert "patterns-one-to-one" in failed(bad)


def test_audit_catches_a_trace_drawing_another_tile() -> None:
    doc = grouped_bar(STATES, [WOMEN, MEN], **KW)
    bad = copy.deepcopy(doc)
    bad["plotly"]["data"][0]["marker"]["pattern"]["path"] = get("lines").path
    assert "patterns-one-to-one" in failed(bad)


def test_audit_catches_weak_ink() -> None:
    doc = grouped_bar(STATES, [WOMEN, MEN], **KW)
    bad = copy.deepcopy(doc)
    for t in bad["plotly"]["data"]:
        t["marker"]["pattern"]["fgcolor"] = "#777777"
    assert "patterns-ink-contrast" in failed(bad)
    # One fill always has black or white at 4.58:1 or more; a very dark and a very light
    # series together leave no ink at 3:1 against both.
    split = Theme("#ffffff", "#1a1a1a", "#008751", "#d9d9d9", series=("#111111", "#eeeeee"))
    weak = grouped_bar(STATES, [WOMEN, MEN], themes={"light": split}, **KW)
    check = next(c for c in weak["audit"]["checks"] if c["id"] == "patterns-ink-contrast")
    assert check["passed"] is False


def test_audit_catches_a_missing_legend() -> None:
    doc = grouped_bar(STATES, [WOMEN, MEN], **KW)
    bad = copy.deepcopy(doc)
    bad["plotly"]["layout"]["showlegend"] = False
    assert "patterns-legend" in failed(bad)


def make_map(**overrides: Any) -> dict[str, Any]:
    return choropleth(NAMES, CODES, MAP_VALUES, **{**MAP_KW, **overrides})


def test_map_sequence_is_ordered_by_ink_weight() -> None:
    assert [p.id for p in MAP_PATTERNS] == ["plain", "dots", "lines", "crosshatch", "solid"]
    assert [has_ink(p) for p in MAP_PATTERNS] == [False, True, True, True, False]
    # Bars keep the 0.2 order, unchanged.
    assert [p.id for p in PATTERNS] == ["dots", "rings", "checks", "lines", "crosshatch"]
    # Fewer classes take an ordered subset, and two no-ink tiles are never neighbours.
    assert [p.id for p in assign_map(2)] == ["plain", "crosshatch"]
    assert [p.id for p in assign_map(3)] == ["plain", "lines", "solid"]
    assert [p.id for p in assign_map(4)] == ["plain", "dots", "crosshatch", "solid"]
    assert assign_map(5) == MAP_PATTERNS
    for tiles in MAP_SEQUENCES.values():
        order = [MAP_PATTERNS.index(t) for t in tiles]
        assert order == sorted(order)
        blank = [i for i, t in enumerate(tiles) if not has_ink(t)]
        assert all(b - a > 1 for a, b in itertools.pairwise(blank))
    with pytest.raises(ValueError, match="2 to 5 classes"):
        assign_map(6)
    assert get("plain").path == "" and get("solid").path == ""


def test_map_patterns_per_class_in_ink_weight_order() -> None:
    doc = make_map()
    assert [c["pattern"] for c in doc["classes"]] == [p.id for p in MAP_PATTERNS]
    assert doc["patterns"]["sequence"] == "ink-weight"
    assert "ink" not in doc["patterns"]  # an ink per class instead
    assert doc["patterns"]["class_ink"] == {
        "light": [None, BLACK, BLACK, BLACK, None],
        "dark": [None, WHITE, BLACK, BLACK, None],
    }
    assert doc["patterns"]["scale"] == pytest.approx(632 / 52 / 12, abs=1e-4)
    cue = next(c for c in doc["audit"]["checks"] if c["id"] == "not-colour-alone")
    assert "own pattern" in cue["note"]
    assert doc["audit"]["passed"] is True and doc["audit"]["warnings"] == 0
    ink = [c for c in doc["audit"]["checks"] if c["id"] == "patterns-ink-contrast"]
    assert {c["theme"] for c in ink} == {"light", "dark"}
    for c in ink:
        assert c["ratios"][0] is None and c["ratios"][-1] is None  # no ink: exempt
        assert all(r >= 3 for r in c["ratios"][1:-1])


def test_fewer_classes_get_an_ordered_subset() -> None:
    doc = make_map(breaks=[2, 4], themes=THREE)
    assert [c["pattern"] for c in doc["classes"]] == ["plain", "lines", "solid"]
    assert doc["audit"]["passed"] is True


def test_green_scheme_keeps_the_02_patterns_and_one_ink() -> None:
    doc = make_map(scheme="green")
    assert [c["pattern"] for c in doc["classes"]] == [p.id for p in PATTERNS]
    assert doc["patterns"]["ink"] == {"light": BLACK, "dark": WHITE}
    assert "class_ink" not in doc["patterns"]
    assert doc["patterns"]["sequence"] == "density-0.2"
    ink = [c for c in doc["audit"]["checks"] if c["id"] == "patterns-ink-contrast"]
    assert all(min(c["ratios"]) >= 3 for c in ink)
    assert doc["audit"]["passed"] is True


def test_map_without_patterns_is_the_01_document() -> None:
    doc = make_map(patterns=False)
    assert "patterns" not in doc
    assert all("pattern" not in c for c in doc["classes"])
    assert not any(c["id"].startswith("patterns-") for c in doc["audit"]["checks"])
    # Not silent: shade alone tells neighbouring classes apart, a warning says so.
    warn = [
        c for c in doc["audit"]["checks"] if c["id"] == "shade-alone" and c["severity"] == "warning"
    ]
    # One check per id: the error check keeps its own id.
    assert sum(c["id"] == "not-colour-alone" for c in doc["audit"]["checks"]) == 1
    assert len(warn) == 1 and warn[0]["passed"] is False
    assert doc["audit"]["passed"] is True


def test_map_patterns_are_auto_by_default() -> None:
    # Five classes or fewer: on, as with patterns=True.
    assert make_map()["patterns"] == make_map(patterns=True)["patterns"]
    assert "patterns" in make_map(breaks=[2, 4], themes=THREE)
    # More than five: off by default, as in 0.1 (which took any number of classes), with
    # the warning; patterns=True still refuses.
    six = make_map(breaks=[1, 2, 3, 4, 6], themes=SIX)
    assert "patterns" not in six
    assert all("pattern" not in c for c in six["classes"])
    assert six["audit"]["passed"] is True
    assert any(
        c["id"] == "shade-alone" and c["severity"] == "warning" and not c["passed"]
        for c in six["audit"]["checks"]
    )
    with pytest.raises(ValueError, match="at most 5"):
        make_map(breaks=[1, 2, 3, 4, 6], themes=SIX, patterns=True)


def test_map_audit_catches_pattern_problems() -> None:
    doc = make_map()
    bad = copy.deepcopy(doc)
    bad["patterns"]["classes"][2] = "dots"
    assert "patterns-one-to-one" in failed(bad)

    bad = copy.deepcopy(doc)
    bad["classes"][2]["pattern"] = None
    assert "patterns-legend" in failed(bad)

    # Per-class ink under 3:1: white on the pale green of class 2 (1.59:1).
    bad = copy.deepcopy(doc)
    bad["patterns"]["class_ink"]["light"][1] = WHITE
    check = next(
        c
        for c in audit(bad)["checks"]
        if c["id"] == "patterns-ink-contrast" and c["theme"] == "light"
    )
    assert check["passed"] is False
    assert check["problems"] == ["class 2: #ffffff on #a1dab4 (1.59:1)"]

    # A class whose tile draws ink must have an ink.
    bad = copy.deepcopy(doc)
    bad["patterns"]["class_ink"]["dark"][2] = None
    assert "patterns-ink-contrast" in failed(bad)

    bad = copy.deepcopy(doc)
    del bad["patterns"]["class_ink"]["light"]
    assert "patterns-ink-contrast" in failed(bad)

    # 3:1 but not the better of black and white: a warning, not an error.
    bad = copy.deepcopy(doc)
    bad["patterns"]["class_ink"]["light"][3] = WHITE  # 4.4:1 on #2c7fb8; black is 4.8:1
    assert "patterns-ink-rule" in failed(bad)
    assert audit(bad)["passed"] is True

    # No-ink tiles side by side would leave two classes told apart by shade alone.
    bad = copy.deepcopy(doc)
    bad["patterns"]["classes"] = ["plain", "solid", "lines", "crosshatch", "dots"]
    for c, pid in zip(bad["classes"], bad["patterns"]["classes"], strict=True):
        c["pattern"] = pid
    check = next(c for c in audit(bad)["checks"] if c["id"] == "patterns-one-to-one")
    assert "two neighbouring classes both have a pattern with no ink" in check["problems"]

    # ... and the fills of no-ink classes must be 3:1 apart.
    bad = copy.deepcopy(doc)
    bad["themes"]["light"]["classes"] = [*bad["themes"]["light"]["classes"][:4], "#c8c8a0"]
    check = next(c for c in audit(bad)["checks"] if c["id"] == "patterns-one-to-one")
    assert any("have no ink" in p for p in check["problems"])


def test_svg_pattern_without_ink() -> None:
    svg = svg_pattern(get("plain"), pattern_id="p0", ink=None, fill="#ffffcc")
    assert "<path" not in svg and 'fill="#ffffcc"' in svg
    with pytest.raises(ValueError, match="needs an ink"):
        svg_pattern(get("dots"), pattern_id="p1", ink=None, fill="#ffffcc")
