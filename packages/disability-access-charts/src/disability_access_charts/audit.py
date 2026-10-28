"""Accessibility audit for chart documents and plain Plotly figures, for CI.

:func:`audit` takes one of:

* a chart document from :func:`~disability_access_charts.plots.bar` or
  :func:`~disability_access_charts.plots.dot` (it has ``plotly`` and ``themes``), or an
  experimental choropleth document from :func:`disability_access_charts.maps.choropleth`
  (``meta.chart_type`` is "choropleth"; see :func:`~disability_access_charts.maps.map_checks`);
* a Plotly figure as a dict (``data`` and ``layout``);
* a Plotly ``Figure`` (anything with ``to_plotly_json`` or ``to_dict``).

It returns ``{"passed": bool, "checks": [...]}``. Every check has an ``id``, the ``wcag``
criterion it stands for, a ``severity`` ("error" or "warning") and ``passed``. The
top-level ``passed`` counts errors only; warnings are things to look at by hand.

For plain figures the colours come from the figure, then its template, then the plotly.js
defaults (colorway, font #444, white background). Colours are read as hex, ``rgb()``,
``rgba()`` (blended over the background) or the 16 basic CSS names; anything else gets a
warning rather than a guess.
"""

from __future__ import annotations

import base64
import re
import struct
from collections.abc import Mapping, Sequence
from typing import Any

from disability_access_charts.contrast import NON_TEXT_MIN, TEXT_MIN, contrast_ratio
from disability_access_charts.describe import (
    ChartData,
    Series,
    check_alt_text,
    mentioned_categories,
    number_tokens,
    shares_of,
)
from disability_access_charts.palettes import Theme

# plotly.js defaults, used when neither the figure nor its template sets a value.
PLOTLY_COLORWAY = (
    "#1f77b4",
    "#ff7f0e",
    "#2ca02c",
    "#d62728",
    "#9467bd",
    "#8c564b",
    "#e377c2",
    "#7f7f7f",
    "#bcbd22",
    "#17becf",
)
PLOTLY_FONT = "#444444"
PLOTLY_BACKGROUND = "#ffffff"

CSS_BASIC = {
    "black": "#000000",
    "silver": "#c0c0c0",
    "gray": "#808080",
    "grey": "#808080",
    "white": "#ffffff",
    "maroon": "#800000",
    "red": "#ff0000",
    "purple": "#800080",
    "fuchsia": "#ff00ff",
    "green": "#008000",
    "lime": "#00ff00",
    "olive": "#808000",
    "yellow": "#ffff00",
    "navy": "#000080",
    "blue": "#0000ff",
    "teal": "#008080",
    "aqua": "#00ffff",
}

_HEX = re.compile(r"^#([0-9a-f]{3,4}|[0-9a-f]{6}|[0-9a-f]{8})$")
_RGB = re.compile(r"^rgba?\(\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)\s*(?:,\s*([\d.]+)\s*)?\)$")


def parse_color(color: str, background: str = PLOTLY_BACKGROUND) -> str | None:
    """A colour as '#rrggbb', with any transparency blended over ``background``.

    Returns None for anything it cannot read (HSL, other CSS names, colour scales).
    """
    c = color.strip().lower()
    c = CSS_BASIC.get(c, c)
    rgba: tuple[float, float, float, float] | None = None
    if m := _HEX.match(c):
        digits = m.group(1)
        if len(digits) in (3, 4):
            digits = "".join(d * 2 for d in digits)
        alpha = int(digits[6:8], 16) / 255 if len(digits) == 8 else 1.0
        rgba = (int(digits[0:2], 16), int(digits[2:4], 16), int(digits[4:6], 16), alpha)
    elif m := _RGB.match(c):
        alpha = float(m.group(4)) if m.group(4) is not None else 1.0
        rgba = (float(m.group(1)), float(m.group(2)), float(m.group(3)), alpha)
    if rgba is None:
        return None
    r, g, b, alpha = rgba
    alpha = min(max(alpha, 0.0), 1.0)
    if alpha < 1:
        bg = parse_color(background) or PLOTLY_BACKGROUND
        br, bgg, bb = (int(bg[i : i + 2], 16) for i in (1, 3, 5))
        r, g, b = (alpha * x + (1 - alpha) * y for x, y in ((r, br), (g, bgg), (b, bb)))
    return "#" + "".join(f"{min(max(round(x), 0), 255):02x}" for x in (r, g, b))


def _contrast_check(
    criterion: str,
    theme: str | None,
    what: str,
    foreground: str,
    background: str,
    minimum: float,
    *,
    against: str = "background",
) -> dict[str, Any]:
    ratio = contrast_ratio(foreground, background)
    check: dict[str, Any] = {
        "id": f"wcag-{criterion}",
        "wcag": criterion,
        "severity": "error",
    }
    if theme is not None:
        check["theme"] = theme
    check.update(
        {
            "description": f"{what} against {against}",
            "foreground": foreground,
            "background": background,
            "ratio": round(ratio, 2),
            "minimum": minimum,
            "passed": ratio >= minimum,
        }
    )
    return check


def _check(
    check_id: str, wcag: str, severity: str, description: str, passed: bool, **extra: Any
) -> dict[str, Any]:
    return {
        "id": check_id,
        "wcag": wcag,
        "severity": severity,
        "description": description,
        "passed": passed,
        **extra,
    }


def theme_checks(themes: Mapping[str, Theme], *, chart_type: str, n_series: int) -> list[dict]:
    """Contrast checks for every theme: marks (or series colours), text and highlight."""
    checks: list[dict[str, Any]] = []
    for name, theme in themes.items():
        if chart_type == "dot":
            for j in range(n_series):
                if j >= len(theme.series):
                    checks.append(
                        _check(
                            "series-colours",
                            "1.4.11",
                            "error",
                            f"Theme {name!r} has no colour for series {j + 1}",
                            False,
                            theme=name,
                        )
                    )
                    continue
                checks.append(
                    _contrast_check(
                        "1.4.11",
                        name,
                        f"Series colour {j + 1}",
                        theme.series[j],
                        theme.background,
                        NON_TEXT_MIN,
                    )
                )
        else:
            checks.append(
                _contrast_check(
                    "1.4.11", name, "Bar colour", theme.mark, theme.background, NON_TEXT_MIN
                )
            )
        checks.append(
            _contrast_check("1.4.3", name, "Text colour", theme.text, theme.background, TEXT_MIN)
        )
        if theme.highlight is not None:
            checks.append(
                _contrast_check(
                    "1.4.11",
                    name,
                    "Highlight colour",
                    theme.highlight,
                    theme.background,
                    NON_TEXT_MIN,
                )
            )
            checks.append(
                _contrast_check(
                    "1.4.11",
                    name,
                    "Highlight colour",
                    theme.highlight,
                    theme.mark,
                    NON_TEXT_MIN,
                    against="bar colour",
                )
            )
    return checks


def alt_text_checks(alt_text: str | None, data: ChartData | None, *, lang: str = "en") -> list:
    """Whether the alt-text exists and whether its numbers and claims match the data."""
    if not alt_text or not alt_text.strip():
        return [_check("alt-text-present", "1.1.1", "error", "The chart has alt-text", False)]
    if data is None:
        return [
            _check(
                "alt-text-not-checked",
                "1.1.1",
                "warning",
                "The alt-text could not be checked: no category data found in the figure",
                False,
            )
        ]
    problems = check_alt_text(alt_text, data, lang=lang)
    errs = [p for p in problems if p.severity == "error"]
    warns = [p for p in problems if p.severity == "warning"]
    vacuous = []
    if not mentioned_categories(alt_text, data, lang=lang) and not number_tokens(
        alt_text, data, lang=lang
    ):
        vacuous.append(
            _check(
                "alt-text-says-little",
                "1.1.1",
                "warning",
                "The alt-text names a category or gives a number",
                False,
            )
        )
    return [
        *vacuous,
        {
            "id": "alt-text-matches-data",
            "wcag": "1.1.1",
            "severity": "error",
            "description": "No number or recognised claim in the alt-text contradicts the data",
            "unverified_numbers": [p.number for p in errs if p.number is not None],
            "problems": [p.to_dict() for p in errs],
            "passed": not errs,
        },
        _check(
            "alt-text-unchecked-claims",
            "1.1.1",
            "warning",
            "Claims in the alt-text that the checker could not test, or results to read with care",
            not warns,
            problems=[p.to_dict() for p in warns],
        ),
    ]


def _hover_data(trace: Mapping[str, Any]) -> bool:
    return any(trace.get(k) not in (None, "", []) for k in ("hovertemplate", "hovertext"))


def interaction_checks(
    traces: Sequence[Mapping[str, Any]], layout: Mapping[str, Any], *, has_table: bool
) -> list[dict[str, Any]]:
    """Hover-only information (SC 2.1.1) and mouse-only zoom and pan."""
    checks: list[dict[str, Any]] = []
    extra = [i for i, t in enumerate(traces) if _hover_data(t) or "customdata" in t]
    default = [
        i
        for i, t in enumerate(traces)
        if i not in extra and t.get("hoverinfo") not in ("skip", "none")
    ]
    if extra and not has_table:
        checks.append(
            _check(
                "hover-only-data",
                "2.1.1",
                "error",
                "Information shown only in hover tooltips, with no table to reach it by keyboard",
                False,
                traces=extra,
            )
        )
    elif extra:
        checks.append(
            _check(
                "hover-only-data",
                "2.1.1",
                "warning",
                "Hover tooltips carry extra text: check the table holds all of it",
                False,
                traces=extra,
            )
        )
    else:
        checks.append(
            _check(
                "hover-only-data", "2.1.1", "error", "No information only in hover tooltips", True
            )
        )
    checks.append(
        _check(
            "hover-default",
            "2.1.1",
            "warning",
            "Hover tooltips are off (they work by mouse only)",
            not default,
            traces=default,
        )
    )
    axes = [k for k in layout if re.fullmatch(r"[xy]axis\d*", k)]
    loose = [k for k in axes if not (layout.get(k) or {}).get("fixedrange")]
    if not axes:
        loose = ["xaxis", "yaxis"]
    checks.append(
        _check(
            "axes-fixed",
            "2.1.1",
            "warning",
            "Zoom and pan are off (they work by mouse only)",
            not loose,
            axes=loose,
        )
    )
    return checks


def _symbols_check(traces: Sequence[Mapping[str, Any]], severity: str) -> dict[str, Any]:
    symbols = [(t.get("marker") or {}).get("symbol", "circle") for t in traces]
    distinct = len(set(map(str, symbols))) == len(symbols)
    return _check(
        "not-colour-alone",
        "1.4.1",
        severity,
        "Each series has its own marker shape, not only its own colour",
        distinct,
    )


def _audit_document(doc: Mapping[str, Any], alt_text: str | None) -> list[dict[str, Any]]:
    themes = {
        name: Theme(**{**t, "series": tuple(t.get("series", ()))})
        for name, t in doc["themes"].items()
    }
    meta = doc.get("meta", {})
    chart_type = meta.get("chart_type", "bar")
    traces = doc["plotly"].get("data", [])
    data = ChartData.from_dict(doc["data"]) if "data" in doc else None
    n_series = len(data.series) if data else len(traces)
    checks = theme_checks(themes, chart_type=chart_type, n_series=n_series)
    text = alt_text if alt_text is not None else doc.get("alt_text")
    checks += alt_text_checks(text, data, lang=meta.get("alt_text_lang", "en"))
    checks += interaction_checks(traces, doc["plotly"].get("layout", {}), has_table="table" in doc)
    if chart_type == "dot" and len(traces) > 1:
        checks.append(_symbols_check(traces, "error"))
    keyboard = doc.get("keyboard")
    if keyboard is not None:
        problems = []
        if keyboard.get("hover_only_data") is False and any(_hover_data(t) for t in traces):
            problems.append("hover_only_data is false, but a trace has hover text")
        if keyboard.get("data_route") == "table":
            table = doc.get("table")
            rows = [str(r[0]) for r in table["rows"]] if table else []
            if data is not None and rows != list(data.categories):
                problems.append("the table does not hold every category, in order")
        checks.append(
            _check(
                "keyboard-metadata",
                "2.1.1",
                "error",
                "The keyboard metadata matches the chart and its table",
                not problems,
                problems=problems,
            )
        )
    checks += data_checks(doc, data)
    return checks


def _close_lists(got: Any, want: Sequence[float] | None, atol: float | None = None) -> bool:
    if want is None or not isinstance(got, (list, tuple)) or len(got) != len(want):
        return False
    try:
        pairs = [(float(x), float(y)) for x, y in zip(got, want, strict=True)]
    except (TypeError, ValueError):
        return False
    return all(
        abs(x - y) <= (atol if atol is not None else 1e-9 * max(1.0, abs(y))) for x, y in pairs
    )


def data_checks(doc: Mapping[str, Any], data: ChartData | None) -> list[dict[str, Any]]:
    """Whether the chart and the table show the numbers in the document's ``data`` block."""
    if data is None:
        return [
            _check(
                "data-block-present",
                "1.1.1",
                "warning",
                "The document has a data block, so its alt-text, chart and table can be checked",
                False,
            )
        ]
    checks: list[dict[str, Any]] = []
    problems: list[str] = []
    categories = list(data.categories)
    traces = doc["plotly"].get("data", [])
    if len(traces) != len(data.series):
        problems.append(f"the chart has {len(traces)} traces for {len(data.series)} series")
    for s, trace in zip(data.series, traces, strict=False):
        cats, values = trace.get("y"), trace.get("x")
        if trace.get("orientation") == "v":
            cats, values = values, cats
        if [str(c) for c in cats or []] != categories:
            problems.append(f"{s.name}: the chart's categories differ from the data")
        if not _close_lists(values, s.values):
            problems.append(f"{s.name}: the chart's values differ from the data")
        if len(data.series) > 1 and trace.get("name") != s.name:
            problems.append(f"{s.name}: the chart's series name is {trace.get('name')!r}")
        bars = trace.get("error_x") if isinstance(trace.get("error_x"), Mapping) else None
        if s.lower is not None and s.upper is not None:
            plus = [hi - v for v, hi in zip(s.values, s.upper, strict=True)]
            minus = [v - lo for v, lo in zip(s.values, s.lower, strict=True)]
            if bars is None or not (
                _close_lists(bars.get("array"), plus)
                and _close_lists(bars.get("arrayminus", bars.get("array")), minus)
            ):
                problems.append(f"{s.name}: the chart's intervals differ from the data")
        elif bars is not None and bars.get("visible", True) and bars.get("array"):
            problems.append(f"{s.name}: the chart draws intervals the data does not have")
    table = doc.get("table")
    if table:
        keys = [c.get("key") for c in table.get("columns", [])]
        rows = table.get("rows", [])
        if [str(r[0]) for r in rows] != categories:
            problems.append("the table's categories differ from the data")
        else:
            several = len(data.series) > 1
            for s in data.series:
                prefix = f"{s.name}:" if several else ""
                for key, want in (("value", s.values), ("lower", s.lower), ("upper", s.upper)):
                    if want is None:
                        continue
                    if prefix + key not in keys:
                        problems.append(f"the table has no {prefix + key!r} column")
                        continue
                    i = keys.index(prefix + key)
                    if not _close_lists([r[i] for r in rows], want):
                        problems.append(f"{s.name}: the table's {key} column differs from the data")
                if data.shares and prefix + "share" in keys:
                    i = keys.index(prefix + "share")
                    if not _close_lists([r[i] for r in rows], shares_of(s.values), atol=0.051):
                        problems.append(f"{s.name}: the table's share column differs from the data")
        total = sum(next(iter(data.series)).values)
        if (
            "total" in table
            and len(data.series) == 1
            and not _close_lists([table["total"]], [total])
        ):
            problems.append("the table's total differs from the data")
    checks.append(
        _check(
            "chart-matches-data",
            "1.1.1",
            "error",
            "The chart and the table show the numbers in the data block",
            not problems,
            problems=problems,
        )
    )
    flat = [
        f"{s.name}: {data.categories[i]}"
        for s in data.series
        if s.lower is not None and s.upper is not None
        for i, v in enumerate(s.values)
        if s.lower[i] == s.upper[i] == v
    ]
    if flat:
        checks.append(
            _check(
                "intervals-zero-width",
                "1.1.1",
                "warning",
                "Intervals with no width (lower = upper = value): every difference from them "
                "passes the interval test",
                False,
                problems=flat,
            )
        )
    return checks


def _plain(value: Any) -> Any:
    """Plotly figure values as plain Python: numpy arrays and base64 typed arrays to lists."""
    if hasattr(value, "tolist"):
        return value.tolist()
    if isinstance(value, Mapping) and "bdata" in value and "dtype" in value:
        codes = {"f8": "d", "f4": "f", "i1": "b", "u1": "B", "i2": "h", "u2": "H"}
        codes |= {"i4": "i", "u4": "I", "i8": "q", "u8": "Q"}
        code = codes.get(str(value["dtype"]).lstrip("<|"))
        if code is None:
            return None
        raw = base64.b64decode(value["bdata"])
        return list(struct.unpack("<" + code * (len(raw) // struct.calcsize(code)), raw))
    if isinstance(value, Mapping):
        return {k: _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    return value


def _figure_dict(fig: Any) -> dict[str, Any] | None:
    if isinstance(fig, Mapping):
        return _plain(fig) if "data" in fig or "layout" in fig else None
    for name in ("to_plotly_json", "to_dict"):
        method = getattr(fig, name, None)
        if callable(method):
            out = method()
            if isinstance(out, Mapping):
                return _plain(out)
    return None


def _decimals(values: Sequence[float]) -> int:
    best = 0
    for v in values:
        text = repr(float(v))
        if "e" not in text and "." in text:
            best = max(best, len(text.split(".")[1].rstrip("0")))
    return min(best, 3)


def chart_data_from_figure(fig: Mapping[str, Any]) -> ChartData | None:
    """Best effort: category data from the bar and scatter traces of a plain figure."""
    traces = fig.get("data") or []
    if not traces or any(t.get("type", "scatter") not in ("bar", "scatter") for t in traces):
        return None
    categories: list[str] | None = None
    series = []
    for i, t in enumerate(traces):
        horizontal = t.get("orientation") == "h"
        cats, vals = (t.get("y"), t.get("x")) if horizontal else (t.get("x"), t.get("y"))
        if not cats or not vals or not all(isinstance(c, str) for c in cats):
            return None
        if not all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in vals):
            return None
        if categories is None:
            categories = list(cats)
        elif list(cats) != categories:
            return None
        series.append(Series(str(t.get("name") or f"trace {i}"), tuple(vals)))
    assert categories is not None
    title = (fig.get("layout") or {}).get("title")
    title_text = title.get("text") if isinstance(title, Mapping) else title
    try:
        return ChartData(
            categories=tuple(categories),
            series=tuple(series),
            unit="number",
            decimals=_decimals([v for s in series for v in s.values]),
            verbatim=(title_text,) if isinstance(title_text, str) and title_text else (),
        )
    except ValueError:
        return None


def _layout_value(layout: Mapping[str, Any], *path: str) -> Any:
    for source in (layout, (layout.get("template") or {}).get("layout") or {}):
        value: Any = source
        for key in path:
            value = value.get(key) if isinstance(value, Mapping) else None
        if value not in (None, ""):
            return value
    return None


def _audit_figure(fig: Mapping[str, Any], alt_text: str | None, has_table: bool) -> list[dict]:
    layout = fig.get("layout") or {}
    traces = fig.get("data") or []
    checks: list[dict[str, Any]] = []
    paper = _layout_value(layout, "paper_bgcolor") or PLOTLY_BACKGROUND
    plot = _layout_value(layout, "plot_bgcolor") or PLOTLY_BACKGROUND
    paper_hex = parse_color(str(paper)) or PLOTLY_BACKGROUND
    plot_hex = parse_color(str(plot), paper_hex)
    font = _layout_value(layout, "font", "color") or PLOTLY_FONT
    colorway = _layout_value(layout, "colorway") or PLOTLY_COLORWAY
    unread: list[str] = []
    if plot_hex is None:
        unread.append(str(plot))
        plot_hex = PLOTLY_BACKGROUND
    text_hex = parse_color(str(font), paper_hex)
    if text_hex is None:
        unread.append(str(font))
    else:
        checks.append(_contrast_check("1.4.3", None, "Text colour", text_hex, paper_hex, TEXT_MIN))
    for i, t in enumerate(traces):
        marker = t.get("marker") or {}
        color = marker.get("color")
        if color is None:
            color = colorway[i % len(colorway)]
        colors = color if isinstance(color, list) else [color]
        label = t.get("name") or f"trace {i}"
        for c in dict.fromkeys(colors):
            if not isinstance(c, str):
                unread.append(f"{label}: numeric colour scale")
                break
            hexed = parse_color(c, plot_hex)
            if hexed is None:
                unread.append(f"{label}: {c}")
                continue
            checks.append(
                _contrast_check(
                    "1.4.11", None, f"Mark colour ({label})", hexed, plot_hex, NON_TEXT_MIN
                )
            )
    if unread:
        checks.append(
            _check(
                "colours-not-read",
                "1.4.11",
                "warning",
                "Some colours could not be read, so their contrast was not checked",
                False,
                colours=unread,
            )
        )
    checks += alt_text_checks(alt_text, chart_data_from_figure(fig) if alt_text else None)
    checks += interaction_checks(traces, layout, has_table=has_table)
    scatters = [t for t in traces if t.get("type", "scatter") == "scatter"]
    if len(scatters) > 1:
        checks.append(_symbols_check(scatters, "warning"))
    return checks


def is_document(obj: Any) -> bool:
    return isinstance(obj, Mapping) and "plotly" in obj and "themes" in obj


def is_map_document(obj: Any) -> bool:
    """An (experimental) choropleth document: no Plotly spec, its own map and themes."""
    meta = obj.get("meta") if isinstance(obj, Mapping) else None
    return isinstance(meta, Mapping) and meta.get("chart_type") == "choropleth" and "map" in obj


def audit(fig: Any, *, alt_text: str | None = None, has_table: bool = False) -> dict[str, Any]:
    """Audit a chart document or a Plotly figure (see the module docstring).

    For a plain figure, pass its ``alt_text`` and say whether the page shows the data in
    a table (``has_table``); a chart document carries both.
    """
    if is_map_document(fig):
        from disability_access_charts.maps import map_checks  # experimental; imports audit

        checks = map_checks(fig, alt_text)
    elif is_document(fig):
        checks = _audit_document(fig, alt_text)
    else:
        figure = _figure_dict(fig)
        if figure is None:
            raise TypeError(
                "expected a chart document, a Plotly figure dict or a plotly Figure, "
                f"got {type(fig).__name__}"
            )
        checks = _audit_figure(figure, alt_text, has_table)
    errors = [c for c in checks if c["severity"] == "error"]
    return {
        "passed": all(c["passed"] for c in errors),
        "warnings": sum(1 for c in checks if c["severity"] == "warning" and not c["passed"]),
        "checks": checks,
    }
