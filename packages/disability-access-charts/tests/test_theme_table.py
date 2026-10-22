import csv
import io
from typing import Any

import pytest
from disability_access_charts import DEFAULT_THEMES, bar, dot, theme, to_csv, to_html

KW: dict[str, Any] = {
    "title": "T <b>",
    "value_label": "Persons",
    "category_label": "Type",
    "source": "S & Co",
}


def test_theme_returns_a_themed_copy_of_a_document() -> None:
    doc = dot(["A", "B"], {"x": [1, 2], "y": [2, 3]}, **KW)
    dark = theme(doc, "dark")
    t = DEFAULT_THEMES["dark"]
    assert dark["plotly"]["layout"]["paper_bgcolor"] == t.background
    assert [tr["marker"]["color"] for tr in dark["plotly"]["data"]] == list(t.series[:2])
    assert doc["plotly"]["layout"]["paper_bgcolor"] == DEFAULT_THEMES["light"].background


def test_theme_on_a_plain_figure_dict() -> None:
    fig = {"data": [{"type": "bar", "x": ["A"], "y": [1]}]}
    out = theme(fig, "dark")
    assert out["data"][0]["marker"]["color"] == DEFAULT_THEMES["dark"].mark
    assert "layout" not in fig


def test_theme_on_a_plotly_figure_keeps_the_type() -> None:
    go = pytest.importorskip("plotly.graph_objects")
    fig = go.Figure(go.Bar(x=["A"], y=[1]))
    out = theme(fig, DEFAULT_THEMES["light"])
    assert isinstance(out, go.Figure)
    assert out.data[0].marker.color == DEFAULT_THEMES["light"].mark


def test_to_html_is_escaped_with_scoped_headers() -> None:
    html = to_html(bar(["A & B", "C"], [1500, 500], **KW))
    assert "<caption>T &lt;b&gt;. Source: S &amp; Co.</caption>" in html
    assert html.count('scope="col"') == 3
    assert '<th scope="row">A &amp; B</th>' in html
    assert '<td class="num">1,500</td>' in html
    assert '<td class="num">75.0</td>' in html


def test_to_csv_has_raw_values() -> None:
    rows = list(csv.reader(io.StringIO(to_csv(bar(["A", "B"], [1500, 500], **KW)))))
    assert rows == [
        ["Type", "Persons", "Share of total (%)"],
        ["A", "1500", "75.0"],
        ["B", "500", "25.0"],
    ]


def test_number_columns_use_their_decimals() -> None:
    doc = bar(["A"], [12.5], lower=[10.0], upper=[14.0], unit="percent", decimals=2, **KW)
    html = to_html(doc["table"])
    assert '<td class="num">12.50</td>' in html
    assert '<td class="num">10.00</td>' in html
