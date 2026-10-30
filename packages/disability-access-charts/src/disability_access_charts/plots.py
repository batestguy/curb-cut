"""Build chart documents: bar charts, grouped bars and dot plots, each with everything a page
needs.

:func:`bar`, :func:`grouped_bar` and :func:`dot` return one JSON-serialisable document, with
no Plotly import (the figure is plain dicts):

* ``plotly``: a Plotly.js figure spec (``data`` + ``layout``), static, no hover-only data;
* ``themes``: light and dark colour sets for the page to apply;
* ``alt_text``: a description built from the data and checked against it;
* ``table``: the same data as an HTML-ready table (caption, columns, rows);
* ``data``: the numbers behind the chart, which the checker and the audit read;
* ``keyboard``: how a keyboard or screen-reader user reaches the data;
* ``audit``: the result of :func:`disability_access_charts.audit.audit` on the document;
* ``meta``: provenance (generator, library version, chart type, source, language);
* ``findings`` (only with ``findings=True``): the statistical findings block, see
  :mod:`disability_access_charts.findings`. The alt-text's "can / cannot show a difference"
  then follows the block's corrected ``extremes`` results instead of the uncorrected test;
* ``patterns`` (bars with patterns on): the pattern tiles, each series' tile and each
  theme's ink, see :mod:`disability_access_charts.patterns`.

Patterns are **off** by default for :func:`bar` (so 0.1 documents are unchanged) and **on**
by default for :func:`grouped_bar`, where they tell the series apart without colour. Dot
plots use marker shapes instead: Plotly has no pattern fill for scatter traces.

:func:`figure` turns a document into a ``plotly.graph_objects.Figure`` (needs the
``plotly`` extra).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import asdict
from typing import Any

from disability_access_charts import _lang
from disability_access_charts._version import __version__
from disability_access_charts.audit import audit
from disability_access_charts.describe import (
    DEFAULT_INTERVAL_LABEL,
    ChartData,
    Series,
    describe,
    format_number,
    format_value,
    shares_of,
)
from disability_access_charts.findings import (
    DEFAULT_Q,
    Reference,
    extreme_verdicts,
    statistical_findings,
)
from disability_access_charts.palettes import DEFAULT_THEMES, SYMBOLS, Theme
from disability_access_charts.patterns import assign, ink_for, plotly_pattern, tile_dict

SCHEMA = "1.0"
_DEFAULT_DECIMALS = {"count": 0, "percent": 1, "number": 1}
PRECISION_LABELS = {
    "reliable": "Reliable",
    "review": "Review: few events",
    "unreliable": "Unreliable",
    "suppressed": "Suppressed",
}
"""How the table writes each precision flag."""


def _themes(themes: Mapping[str, Theme] | None) -> dict[str, Theme]:
    themes = dict(themes or DEFAULT_THEMES)
    if "light" not in themes:
        raise ValueError("a 'light' theme is required; it is the default rendering")
    return themes


def _error_bars(series: Series, color: str) -> dict[str, Any]:
    assert series.lower is not None and series.upper is not None
    return {
        "type": "data",
        "symmetric": False,
        "array": [hi - v for v, hi in zip(series.values, series.upper, strict=True)],
        "arrayminus": [v - lo for v, lo in zip(series.values, series.lower, strict=True)],
        "color": color,
        "thickness": 1.5,
        "width": 6,
    }


def _layout(data: ChartData, light: Theme, value_label: str, *, legend: bool) -> dict[str, Any]:
    axis_font = {"color": light.text, "size": 14}
    xaxis: dict[str, Any] = {
        "title": {"text": value_label, "font": axis_font},
        "gridcolor": light.grid,
        "zeroline": False,
        "fixedrange": True,
    }
    if data.unit == "count":
        xaxis["tickformat"] = ",~s"
    elif data.unit == "percent":
        xaxis["ticksuffix"] = "%"
    labels = data.unit == "count" or not data.has_interval
    layout: dict[str, Any] = {
        "title": {"text": ""},  # the page's <figcaption> carries the title
        "paper_bgcolor": light.background,
        "plot_bgcolor": light.background,
        "font": {"color": light.text, "size": 14},
        "margin": {"l": 10, "r": 90 if labels else 30, "t": 10, "b": 60},
        "xaxis": xaxis,
        "yaxis": {"autorange": "reversed", "automargin": True, "fixedrange": True},
        "showlegend": legend,
    }
    if legend:
        layout["legend"] = {"orientation": "h", "y": -0.25, "font": {"color": light.text}}
    return layout


def _table(data: ChartData, title: str, source: str, value_label: str) -> dict[str, Any]:
    counts = data.unit == "count"
    value_type: dict[str, Any] = (
        {"type": "integer"} if counts else {"type": "number", "decimals": data.decimals}
    )
    columns: list[dict[str, Any]] = [
        {"key": "category", "label": data.category_label, "type": "text"}
    ]
    several = len(data.series) > 1
    for s in data.series:
        prefix = f"{s.name}: " if several else ""
        key = f"{s.name}:" if several else ""
        columns.append({"key": f"{key}value", "label": f"{prefix}{value_label}", **value_type})
        if s.has_interval:
            for bound in ("lower", "upper"):
                columns.append(
                    {
                        "key": f"{key}{bound}",
                        "label": f"{prefix}{data.interval_label}, {bound}",
                        **value_type,
                    }
                )
        if data.shares:
            columns.append(
                {"key": f"{key}share", "label": f"{prefix}Share of total (%)", "type": "percent"}
            )
        if s.precision is not None:
            columns.append(
                {"key": f"{key}precision", "label": f"{prefix}Precision", "type": "text"}
            )
    rows: list[list[Any]] = []
    for i, category in enumerate(data.categories):
        row: list[Any] = [category]
        for s in data.series:
            row.append(s.values[i])
            if s.lower is not None and s.upper is not None:
                row += [s.lower[i], s.upper[i]]
            if data.shares:
                row.append(round(shares_of(s.values)[i], 1))
            if s.precision is not None:
                row.append(PRECISION_LABELS[s.precision[i]])
        rows.append(row)
    table: dict[str, Any] = {
        "caption": f"{title}. Source: {source}.",
        "columns": columns,
        "rows": rows,
    }
    if counts and data.shares and not several:
        table["total"] = sum(data.series[0].values)
    return table


def _document(
    data: ChartData,
    *,
    chart_type: str,
    plotly: dict[str, Any],
    themes: dict[str, Theme],
    title: str,
    source: str,
    value_label: str,
    chart_id: str,
    lang: str,
    generator: str,
    findings: dict[str, Any] | None = None,
    patterns: dict[str, Any] | None = None,
) -> dict[str, Any]:
    # With findings, "can / cannot show a difference" in the alt-text follows the findings'
    # corrected extremes results, so the two never disagree.
    verdicts = None if findings is None else extreme_verdicts(findings, data)
    alt_text = describe(
        data, chart_type=chart_type, title=title, source=source, lang=lang, verdicts=verdicts
    )
    doc: dict[str, Any] = {
        "id": chart_id,
        "title": title,
        "plotly": plotly,
        "themes": {name: asdict(t) for name, t in themes.items()},
        "alt_text": alt_text,
        "table": _table(data, title, source, value_label),
        "data": data.to_dict(),
        "keyboard": {
            # The chart is a static image: no zoom, pan or hover, nothing to tab to. Every
            # value is in the table, which the page renders as real HTML.
            "interactive": False,
            "hover_only_data": False,
            "data_route": "table",
        },
        "meta": {
            "experimental": False,  # kept from the P1 file shape; true only from experimental.py
            "generator": generator,
            "library_version": __version__,
            "schema": SCHEMA,
            "chart_type": chart_type,
            "source": source,
            "alt_text_source": "data",
            "alt_text_lang": lang,
        },
    }
    if findings is not None:
        doc["findings"] = findings
    if patterns is not None:
        doc["patterns"] = patterns
    doc["audit"] = audit(doc)
    return doc


def _findings(
    data: ChartData,
    on: bool,
    reference: Reference | None,
    withheld: Sequence[str],
    q: float,
    lang: str,
) -> dict[str, Any] | None:
    if not on:
        if reference is not None or withheld:
            raise ValueError("reference and withheld are used only with findings=True")
        return None
    return statistical_findings(data, reference=reference, withheld=withheld, q=q, lang=lang)


def _bar_patterns(
    traces: Sequence[dict[str, Any]], themes: Mapping[str, Theme], single: bool
) -> dict[str, Any]:
    """Give each bar trace its own tile, in the light theme's colours; return the block."""
    tiles = assign(len(traces))
    fills = {
        name: [t.mark] if single else list(t.series[: len(traces)]) for name, t in themes.items()
    }
    ink = {name: ink_for(colours) for name, colours in fills.items()}
    for trace, tile, fill in zip(traces, tiles, fills["light"], strict=True):
        trace["marker"]["pattern"] = plotly_pattern(tile, ink=ink["light"], fill=fill)
    return {
        "tiles": {tile.id: tile_dict(tile) for tile in tiles},
        "series": [tile.id for tile in tiles],
        "ink": ink,
    }


def bar(
    categories: Sequence[str],
    values: Sequence[float],
    *,
    title: str,
    value_label: str,
    category_label: str,
    source: str,
    lower: Sequence[float] | None = None,
    upper: Sequence[float] | None = None,
    unit: str = "count",
    decimals: int | None = None,
    interval_label: str = DEFAULT_INTERVAL_LABEL,
    parts_of_whole: bool | None = None,
    themes: Mapping[str, Theme] | None = None,
    chart_id: str = "chart",
    lang: str = "en",
    glossary: Mapping[str, str] | None = None,
    precision: Sequence[str] | None = None,
    patterns: bool = False,
    findings: bool = False,
    reference: Reference | None = None,
    withheld: Sequence[str] = (),
    fdr_q: float = DEFAULT_Q,
) -> dict[str, Any]:
    """A horizontal bar-chart document (see the module docstring).

    Bars are drawn in the order given, top to bottom. ``unit`` is "count" (whole numbers,
    with shares of the total), "percent" or "number". ``lower`` and ``upper`` add an
    interval to each bar (labelled ``interval_label``); bars with intervals carry no value
    labels, since they would collide with the whiskers. ``parts_of_whole`` says the
    categories split one total (the default for counts): shares are given, and interval
    comparisons warn that the groups are not independent.

    New in 0.2: ``precision`` (a flag per bar, see :class:`Series`) adds a table column and
    feeds the findings; ``patterns=True`` fills the bars with a pattern tile; and
    ``findings=True`` adds the statistical findings block (needs intervals), with an
    optional ``reference`` (overall value), ``withheld`` (categories left out of the chart)
    and false discovery rate ``fdr_q``.
    """
    _lang.get(lang)
    themes = _themes(themes)
    shares = unit == "count" if parts_of_whole is None else parts_of_whole
    data = ChartData(
        categories=tuple(categories),
        series=(
            Series(
                value_label,
                tuple(values),
                None if lower is None else tuple(lower),
                None if upper is None else tuple(upper),
                None if precision is None else tuple(precision),
            ),
        ),
        unit=unit,
        decimals=_DEFAULT_DECIMALS.get(unit, 1) if decimals is None else decimals,
        shares=shares,
        verbatim=(title, source),
        interval_label=interval_label,
        category_label=category_label,
        glossary=dict(glossary or {}),
    )
    series = data.series[0]
    light = themes["light"]
    if series.has_interval:
        text = ["" for _ in series.values]
    elif unit == "count":
        text = [format_number(v) for v in series.values]
    else:
        text = [format_value(v, data) for v in series.values]
    trace: dict[str, Any] = {
        "type": "bar",
        "orientation": "h",
        "x": list(series.values),
        "y": list(data.categories),
        "marker": {"color": light.mark},
        "text": text,
        "textposition": "outside",
        "cliponaxis": False,
        "hoverinfo": "skip",
    }
    if series.has_interval:
        trace["error_x"] = _error_bars(series, light.text)
    layout = _layout(data, light, value_label, legend=False)
    layout["bargap"] = 0.25
    block = _bar_patterns([trace], themes, single=True) if patterns else None
    return _document(
        data,
        chart_type="bar",
        plotly={"data": [trace], "layout": layout},
        themes=themes,
        title=title,
        source=source,
        value_label=value_label,
        chart_id=chart_id,
        lang=lang,
        generator="disability_access_charts.plots.bar",
        findings=_findings(data, findings, reference, withheld, fdr_q, lang),
        patterns=block,
    )


def _series_items(
    series: Sequence[Series] | Mapping[str, Sequence[float]],
) -> tuple[Series, ...]:
    if isinstance(series, Mapping):
        return tuple(Series(name, tuple(values)) for name, values in series.items())
    return tuple(series)


def grouped_bar(
    categories: Sequence[str],
    series: Sequence[Series] | Mapping[str, Sequence[float]],
    *,
    title: str,
    value_label: str,
    category_label: str,
    source: str,
    unit: str = "percent",
    decimals: int | None = None,
    interval_label: str = DEFAULT_INTERVAL_LABEL,
    parts_of_whole: bool = False,
    patterns: bool = True,
    themes: Mapping[str, Theme] | None = None,
    chart_id: str = "chart",
    lang: str = "en",
    glossary: Mapping[str, str] | None = None,
    findings: bool = False,
    reference: Reference | None = None,
    withheld: Sequence[str] = (),
    fdr_q: float = DEFAULT_Q,
) -> dict[str, Any]:
    """A grouped horizontal bar-chart document: one group of bars per category, one bar per
    series (new in 0.2).

    ``series`` is as for :func:`dot`. Each series has its own colour and, with
    ``patterns=True`` (the default), its own pattern tile, shown in the legend too, so the
    series are told apart without colour (at most five). The alt-text describes each series
    as the dot plot's does. Findings work as for :func:`bar`, with the ``gaps`` family
    comparing the series within each category.
    """
    _lang.get(lang)
    themes = _themes(themes)
    items = _series_items(series)
    if len(items) < 2:
        raise ValueError("grouped bars need at least two series; use bar() for one")
    for name, t in themes.items():
        if len(items) > len(t.series):
            raise ValueError(
                f"theme {name!r} has {len(t.series)} series colours for {len(items)} series"
            )
    data = ChartData(
        categories=tuple(categories),
        series=items,
        unit=unit,
        decimals=_DEFAULT_DECIMALS.get(unit, 1) if decimals is None else decimals,
        shares=parts_of_whole,
        verbatim=(title, source),
        interval_label=interval_label,
        category_label=category_label,
        glossary=dict(glossary or {}),
    )
    light = themes["light"]
    traces = []
    for j, s in enumerate(data.series):
        labels = (
            ["" for _ in s.values] if s.has_interval else [format_value(v, data) for v in s.values]
        )
        trace: dict[str, Any] = {
            "type": "bar",
            "orientation": "h",
            "name": s.name,
            "x": list(s.values),
            "y": list(data.categories),
            "marker": {"color": light.series[j]},
            "text": labels,
            "textposition": "outside",
            "cliponaxis": False,
            "hoverinfo": "skip",
        }
        if s.has_interval:
            trace["error_x"] = _error_bars(s, light.text)
        traces.append(trace)
    layout = _layout(data, light, value_label, legend=True)
    layout["barmode"] = "group"
    layout["bargap"] = 0.25
    layout["bargroupgap"] = 0.1
    block = _bar_patterns(traces, themes, single=False) if patterns else None
    return _document(
        data,
        chart_type="bar",
        plotly={"data": traces, "layout": layout},
        themes=themes,
        title=title,
        source=source,
        value_label=value_label,
        chart_id=chart_id,
        lang=lang,
        generator="disability_access_charts.plots.grouped_bar",
        findings=_findings(data, findings, reference, withheld, fdr_q, lang),
        patterns=block,
    )


def dot(
    categories: Sequence[str],
    series: Sequence[Series] | Mapping[str, Sequence[float]],
    *,
    title: str,
    value_label: str,
    category_label: str,
    source: str,
    unit: str = "percent",
    decimals: int | None = None,
    interval_label: str = DEFAULT_INTERVAL_LABEL,
    parts_of_whole: bool = False,
    themes: Mapping[str, Theme] | None = None,
    chart_id: str = "chart",
    lang: str = "en",
    glossary: Mapping[str, str] | None = None,
    findings: bool = False,
    reference: Reference | None = None,
    withheld: Sequence[str] = (),
    fdr_q: float = DEFAULT_Q,
) -> dict[str, Any]:
    """A dot-plot document: one row per category, one dot (and optional interval) per series.

    ``series`` is a sequence of :class:`Series` (which may carry ``lower`` and ``upper``),
    or a mapping of series name to values. Each series gets its own colour and marker
    shape, so they are told apart without colour, and the legend is shown. Series may carry
    ``precision`` flags. ``findings=True`` adds the statistical findings block (new in 0.2;
    see :func:`bar`).
    """
    _lang.get(lang)
    themes = _themes(themes)
    items = _series_items(series)
    for name, t in themes.items():
        if len(items) > len(t.series):
            raise ValueError(
                f"theme {name!r} has {len(t.series)} series colours for {len(items)} series"
            )
    if len(items) > len(SYMBOLS):
        raise ValueError(f"at most {len(SYMBOLS)} series (one marker shape each)")
    data = ChartData(
        categories=tuple(categories),
        series=items,
        unit=unit,
        decimals=_DEFAULT_DECIMALS.get(unit, 1) if decimals is None else decimals,
        shares=parts_of_whole,
        verbatim=(title, source),
        interval_label=interval_label,
        category_label=category_label,
        glossary=dict(glossary or {}),
    )
    light = themes["light"]
    traces = []
    for j, s in enumerate(data.series):
        trace: dict[str, Any] = {
            "type": "scatter",
            "mode": "markers",
            "name": s.name,
            "x": list(s.values),
            "y": list(data.categories),
            # Horizontal, so layout.scattermode "group" sets the series side by side.
            "orientation": "h",
            "marker": {"color": light.series[j], "symbol": SYMBOLS[j], "size": 11},
            "cliponaxis": False,
            "hoverinfo": "skip",
        }
        if s.has_interval:
            # The whiskers take the series colour, so each interval is tied to its dot.
            trace["error_x"] = _error_bars(s, light.series[j])
        traces.append(trace)
    layout = _layout(data, light, value_label, legend=len(data.series) > 1)
    if len(data.series) > 1:
        # Without this, every series sits on the category's line and the whiskers overlap.
        layout["scattermode"] = "group"
        layout["scattergap"] = 0.4
    return _document(
        data,
        chart_type="dot",
        plotly={"data": traces, "layout": layout},
        themes=themes,
        title=title,
        source=source,
        value_label=value_label,
        chart_id=chart_id,
        lang=lang,
        generator="disability_access_charts.plots.dot",
        findings=_findings(data, findings, reference, withheld, fdr_q, lang),
    )


def figure(doc: Mapping[str, Any], theme_name: str = "light") -> Any:
    """The document's chart as a ``plotly.graph_objects.Figure``, themed.

    Needs the ``plotly`` extra: ``pip install "disability-access-charts[plotly]"``.
    """
    try:
        import plotly.graph_objects as go
    except ImportError as exc:  # pragma: no cover - depends on the environment
        raise ImportError(
            'figure() needs Plotly: pip install "disability-access-charts[plotly]"'
        ) from exc
    from disability_access_charts.theme import theme

    themed = theme(doc, theme_name)
    return go.Figure(themed["plotly"])
