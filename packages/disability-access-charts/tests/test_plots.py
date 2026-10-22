import json
import math
from typing import Any

import pytest
from disability_access_charts import (
    DEFAULT_THEMES,
    ChartData,
    Series,
    Theme,
    __version__,
    bar,
    check_alt_text,
    dot,
)

KW: dict[str, Any] = {
    "title": "Prevalence by state (illustrative)",
    "value_label": "Prevalence (%)",
    "category_label": "State",
    "source": "Synthetic",
}
CATS = ["Kano", "Lagos", "Oyo"]


def test_bar_document_shape_is_additive() -> None:
    doc = json.loads(json.dumps(bar(["A", "B"], [3, 1], **KW)))
    assert set(doc) >= {"id", "title", "plotly", "themes", "alt_text", "table", "audit", "meta"}
    assert set(doc) >= {"data", "keyboard"}
    meta = doc["meta"]
    assert meta["experimental"] is False
    assert meta["library_version"] == __version__
    assert meta["schema"] == "1.0"
    assert meta["chart_type"] == "bar"
    assert meta["alt_text_source"] == "data"
    assert meta["alt_text_lang"] == "en"
    assert doc["keyboard"] == {
        "interactive": False,
        "hover_only_data": False,
        "data_route": "table",
    }
    assert doc["themes"]["light"]["series"] == list(DEFAULT_THEMES["light"].series)
    assert doc["audit"]["passed"] is True


def test_bar_with_intervals_has_whiskers_and_no_value_labels() -> None:
    doc = bar(
        CATS, [12.3, 11.9, 6.0], lower=[10.1, 9.8, 4.9], upper=[14.5, 14.0, 7.1],
        unit="percent", **KW,
    )  # fmt: skip
    trace = doc["plotly"]["data"][0]
    assert trace["text"] == ["", "", ""]
    assert trace["error_x"]["array"] == pytest.approx([2.2, 2.1, 1.1])
    assert trace["error_x"]["arrayminus"] == pytest.approx([2.2, 2.1, 1.1])
    assert trace["error_x"]["color"] == DEFAULT_THEMES["light"].text
    labels = [c["label"] for c in doc["table"]["columns"]]
    assert labels == [
        "State",
        "Prevalence (%)",
        "95% confidence interval, lower",
        "95% confidence interval, upper",
    ]
    assert doc["table"]["columns"][1] == {
        "key": "value", "label": "Prevalence (%)", "type": "number", "decimals": 1,
    }  # fmt: skip
    assert doc["table"]["rows"][0] == ["Kano", 12.3, 10.1, 14.5]
    assert "highest estimate" in doc["alt_text"].lower()
    assert doc["audit"]["passed"] is True


def test_dot_plot_series_colours_symbols_and_legend() -> None:
    doc = dot(CATS, {"Women": [1.0, 2.0, 3.0], "Men": [1.5, 2.5, 3.5]}, **KW)
    traces = doc["plotly"]["data"]
    assert [t["name"] for t in traces] == ["Women", "Men"]
    assert [t["marker"]["color"] for t in traces] == list(DEFAULT_THEMES["light"].series[:2])
    assert len({t["marker"]["symbol"] for t in traces}) == 2
    assert all(t["hoverinfo"] == "skip" and t["mode"] == "markers" for t in traces)
    assert doc["plotly"]["layout"]["showlegend"] is True
    assert doc["meta"]["chart_type"] == "dot"
    assert [c["key"] for c in doc["table"]["columns"]] == ["category", "Women:value", "Men:value"]
    assert doc["audit"]["passed"] is True
    data = ChartData.from_dict(doc["data"])
    assert check_alt_text(doc["alt_text"], data) == []


def test_dot_plot_with_intervals() -> None:
    series = [
        Series("Women", (12.3, 11.9, 6.0), (10.1, 9.8, 4.9), (14.5, 14.0, 7.1)),
        Series("Men", (10.0, 9.0, 5.0), (8.0, 7.0, 4.0), (12.0, 11.0, 6.0)),
    ]
    doc = dot(CATS, series, **KW)
    assert all("error_x" in t for t in doc["plotly"]["data"])
    assert doc["audit"]["passed"] is True
    assert check_alt_text(doc["alt_text"], ChartData.from_dict(doc["data"])) == []
    # Series sit side by side, and each whisker takes its series' colour, so the
    # intervals neither overlap nor lose their link to their dot.
    assert doc["plotly"]["layout"]["scattermode"] == "group"
    for j, trace in enumerate(doc["plotly"]["data"]):
        assert trace["orientation"] == "h"
        assert trace["error_x"]["color"] == trace["marker"]["color"]
        assert trace["error_x"]["color"] == DEFAULT_THEMES["light"].series[j]


def test_themed_dot_whiskers_follow_the_series_colour() -> None:
    from disability_access_charts import theme

    series = [Series("Women", (5.0, 6.0), (4.0, 5.0), (6.0, 7.0)), Series("Men", (4.0, 5.0))]
    dark = DEFAULT_THEMES["dark"]
    themed = theme(dot(["A", "B"], series, **KW), "dark")
    assert themed["plotly"]["data"][0]["error_x"]["color"] == dark.series[0]
    # Bar whiskers keep the text colour.
    bars = theme(
        bar(["A", "B"], [5.0, 6.0], lower=[4.0, 5.0], upper=[6.0, 7.0], unit="percent", **KW),
        "dark",
    )
    assert bars["plotly"]["data"][0]["error_x"]["color"] == dark.text


def test_every_axis_is_fixed() -> None:
    for doc in (bar(["A"], [1], **KW), dot(["A", "B"], {"x": [1, 2]}, **KW)):
        layout = doc["plotly"]["layout"]
        assert layout["xaxis"]["fixedrange"] and layout["yaxis"]["fixedrange"]


@pytest.mark.parametrize(
    "kwargs",
    [
        {"categories": [], "values": []},
        {"categories": ["A"], "values": [1, 2]},
        {"categories": ["A", "A"], "values": [1, 2]},
        {"categories": ["A"], "values": [math.nan]},
        {"categories": ["A"], "values": [math.inf]},
        {"categories": ["A"], "values": [-1]},
        {"categories": ["A"], "values": [0]},
        {"categories": ["A"], "values": [5], "lower": [6], "upper": [7]},
        {"categories": ["A"], "values": [5], "lower": [4]},
        {"categories": ["A"], "values": [5], "unit": "ratio"},
    ],
)
def test_bar_rejects_bad_input(kwargs: dict) -> None:
    with pytest.raises(ValueError):
        bar(**kwargs, **KW)


def test_dot_rejects_more_series_than_colours() -> None:
    few = {
        "light": Theme("#ffffff", "#000000", "#008751", "#ccc", series=("#0072b2",)),
    }
    with pytest.raises(ValueError, match="series colours"):
        dot(CATS, {"a": [1, 2, 3], "b": [1, 2, 3]}, themes=few, **KW)


def test_a_light_theme_is_required() -> None:
    with pytest.raises(ValueError, match="light"):
        bar(["A"], [1], themes={"dark": DEFAULT_THEMES["dark"]}, **KW)


def test_unknown_language_is_rejected() -> None:
    with pytest.raises(ValueError, match="unknown language"):
        bar(["A"], [1], lang="ig", **KW)


def test_figure_needs_and_uses_plotly() -> None:
    go = pytest.importorskip("plotly.graph_objects")
    from disability_access_charts import figure

    fig = figure(bar(["A", "B"], [3, 1], **KW), "dark")
    assert isinstance(fig, go.Figure)
    assert fig.layout.paper_bgcolor == DEFAULT_THEMES["dark"].background
