import copy
from typing import Any

import pytest
from disability_access_charts import audit, bar, dot
from disability_access_charts.audit import parse_color

KW: dict[str, Any] = {"title": "T", "value_label": "V", "category_label": "C", "source": "S"}


def failed(result: dict, severity: str | None = None) -> list[str]:
    return [
        c["id"]
        for c in result["checks"]
        if not c["passed"] and (severity is None or c["severity"] == severity)
    ]


def test_every_check_has_the_common_fields() -> None:
    for doc in (bar(["A", "B"], [2, 1], **KW), dot(["A", "B"], {"x": [1, 2], "y": [2, 3]}, **KW)):
        for check in doc["audit"]["checks"]:
            assert {"id", "wcag", "severity", "passed"} <= set(check)
            assert check["severity"] in ("error", "warning")


def test_document_audit_catches_tampered_alt_text() -> None:
    doc = bar(["A", "B"], [2, 1], **KW)
    doc["alt_text"] = doc["alt_text"].replace("Largest: A, 2", "Largest: B, 2")
    result = audit(doc)
    assert result["passed"] is False
    assert "alt-text-matches-data" in failed(result, "error")


def test_document_audit_catches_hover_data_and_a_short_table() -> None:
    doc = bar(["A", "B"], [2, 1], **KW)
    bad = copy.deepcopy(doc)
    bad["plotly"]["data"][0]["hovertemplate"] = "%{y}: %{x}"
    assert "keyboard-metadata" in failed(audit(bad), "error")
    short = copy.deepcopy(doc)
    short["table"]["rows"] = short["table"]["rows"][:1]
    assert "keyboard-metadata" in failed(audit(short), "error")


def test_dot_plot_markers_must_differ_in_shape() -> None:
    doc = dot(["A", "B"], {"x": [1, 2], "y": [2, 3]}, **KW)
    for trace in doc["plotly"]["data"]:
        trace["marker"]["symbol"] = "circle"
    assert "not-colour-alone" in failed(audit(doc), "error")


def test_plain_figure_dict_defaults_and_problems() -> None:
    fig = {"data": [{"type": "bar", "x": ["A", "B"], "y": [3, 1]}], "layout": {}}
    result = audit(fig, alt_text="Largest: A, 3.")
    # plotly.js default blue on white passes; default hover and zoom only warn.
    assert result["passed"] is True
    assert set(failed(result, "warning")) == {"hover-default", "axes-fixed"}
    assert audit(fig)["passed"] is False  # no alt-text
    assert "alt-text-present" in failed(audit(fig), "error")


def test_plain_figure_wrong_claim_and_low_contrast() -> None:
    fig = {
        "data": [{"type": "bar", "x": ["A", "B"], "y": [3, 1], "marker": {"color": "#f0e442"}}],
        "layout": {"xaxis": {"fixedrange": True}, "yaxis": {"fixedrange": True}},
    }
    result = audit(fig, alt_text="Largest: B, 1.")
    assert set(failed(result, "error")) == {"wcag-1.4.11", "alt-text-matches-data"}


def test_plain_figure_hover_template_without_a_table_is_an_error() -> None:
    fig = {"data": [{"type": "bar", "x": ["A"], "y": [1], "hovertemplate": "%{x}"}]}
    assert "hover-only-data" in failed(audit(fig, alt_text="A, 1."), "error")
    assert "hover-only-data" in failed(audit(fig, alt_text="A, 1.", has_table=True), "warning")


def test_unreadable_figures_warn_about_unchecked_alt_text_and_colours() -> None:
    fig = {"data": [{"type": "pie", "values": [1, 2], "marker": {"color": "hsl(0,0,0)"}}]}
    result = audit(fig, alt_text="A pie.")
    assert {"alt-text-not-checked", "colours-not-read"} <= set(failed(result, "warning"))


def test_plotly_figure_object_uses_its_template() -> None:
    go = pytest.importorskip("plotly.graph_objects")
    fig = go.Figure(go.Bar(x=["A", "B"], y=[3, 1]))
    result = audit(fig, alt_text="Largest: A, 3.")
    mark = next(c for c in result["checks"] if c["id"] == "wcag-1.4.11")
    assert mark["background"] == "#e5ecf6"  # the plotly template's plot background


@pytest.mark.parametrize(
    ("colour", "expected"),
    [
        ("#FFF", "#ffffff"),
        ("#00000080", "#7f7f7f"),
        ("rgb(0, 114, 178)", "#0072b2"),
        ("rgba(0,0,0,0.5)", "#808080"),
        ("navy", "#000080"),
        ("hsl(0, 0%, 0%)", None),
        ("rebeccapurple", None),
    ],
)
def test_parse_color(colour: str, expected: str | None) -> None:
    assert parse_color(colour) == expected


def test_rejects_unknown_input() -> None:
    with pytest.raises(TypeError):
        audit(42)


def test_chart_and_table_must_match_the_data_block() -> None:
    doc = bar(["A", "B", "C"], [50, 30, 20], **KW)
    assert "chart-matches-data" not in failed(audit(doc))
    chart = copy.deepcopy(doc)
    chart["plotly"]["data"][0]["x"] = [5, 300, 2000]
    assert "chart-matches-data" in failed(audit(chart), "error")
    table = copy.deepcopy(doc)
    table["table"]["rows"][0][1] = 999
    assert "chart-matches-data" in failed(audit(table), "error")
    ci = bar(["A", "B"], [5.0, 3.0], lower=[4.0, 2.0], upper=[6.0, 4.0], unit="percent", **KW)
    assert "chart-matches-data" not in failed(audit(ci))
    whiskers = copy.deepcopy(ci)
    whiskers["plotly"]["data"][0]["error_x"]["array"] = [9.0, 9.0]
    assert "chart-matches-data" in failed(audit(whiskers), "error")


def test_a_missing_data_block_and_vacuous_alt_text_warn() -> None:
    doc = bar(["A", "B"], [2, 1], **KW)
    no_data = copy.deepcopy(doc)
    del no_data["data"]
    assert "data-block-present" in failed(audit(no_data), "warning")
    vague = copy.deepcopy(doc)
    vague["alt_text"] = "This chart shows something."
    assert "alt-text-says-little" in failed(audit(vague), "warning")


def test_zero_width_intervals_warn() -> None:
    doc = bar(["A", "B"], [5.0, 3.0], lower=[5.0, 2.0], upper=[5.0, 4.0], unit="percent", **KW)
    assert "intervals-zero-width" in failed(doc["audit"], "warning")


def test_table_total_must_match_the_data() -> None:
    doc = bar(["A", "B"], [2, 1], **KW)
    bad = copy.deepcopy(doc)
    bad["table"]["total"] = 4
    assert "chart-matches-data" in failed(audit(bad), "error")
