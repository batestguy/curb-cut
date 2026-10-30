"""Draw a ``disability_access_charts`` dot-plot document as a static SVG string.

The state pages load no Plotly, so ``build_state_pages.py`` draws each state's dot plot at
build time from the chart document itself: its ``data`` block (categories, series values,
interval bounds, decimals), the Plotly traces' marker shapes (one per series, so series are
told apart without colour) and the axis title. Colours are not written into the SVG: each
mark takes a CSS custom property (``--dot-s0``, ``--dot-grid``, ...) that the page sets from
the document's ``themes`` for light and dark (:func:`theme_css`), so the drawing always uses
the audited colours of the current scheme. Every value also gets a direct label in the text
colour.

The SVG is decorative to assistive technology (``aria-hidden``): the page names the figure
with the document's alt-text and always shows the document's data table.
"""

from __future__ import annotations

import html
import math
from collections.abc import Mapping, Sequence
from typing import Any

WIDTH = 420  # SVG user units; the page scales the drawing to its container
LABEL_H = 22  # category label line above each row's dots
SERIES_GAP = 20  # vertical distance between the series of one row
ROW_PAD = 12  # space after a row
AXIS_H = 52  # tick labels and the axis title under the plot
PLOT_LEFT = 8
PLOT_RIGHT = WIDTH - 60  # room right of the largest upper bound for its direct label
MARKER = 6.0  # marker half-size

_STEPS = (1, 2, 2.5, 5, 10)


def nice_max(value: float, ticks: int = 4) -> tuple[float, float]:
    """A round axis maximum at or above ``value`` and its tick step (about ``ticks`` ticks)."""
    if value <= 0:
        return 1.0, 0.25
    raw = value / ticks
    magnitude = 10 ** math.floor(math.log10(raw))
    step = next(s * magnitude for s in _STEPS if s * magnitude >= raw - 1e-12)
    top = math.ceil(value / step - 1e-9) * step
    return top, step


def _fmt(value: float, decimals: int) -> str:
    text = f"{value:.{decimals}f}"
    return "0" if float(text) == 0 and text.startswith("-") else text


def label_text(value: float, decimals: int) -> str:
    """A direct label: a value above 0 that would round to 0 reads "<0.1" (at 1 decimal),
    not a misleading "0.0"; exactly 0 stays "0.0"."""
    smallest = 10**-decimals
    if 0 < value < smallest / 2:
        return f"<{smallest:.{decimals}f}"
    return _fmt(value, decimals)


def _num(value: float) -> str:
    return f"{value:.1f}".rstrip("0").rstrip(".")


def marker(symbol: str, x: float, y: float, cls: str) -> str:
    """One marker in the Plotly shape ``symbol`` (circle, diamond, square, triangle-up, x, star)."""
    r = MARKER
    if symbol == "circle":
        return f'<circle class="{cls}" cx="{_num(x)}" cy="{_num(y)}" r="{_num(r)}"/>'
    if symbol == "square":
        s = r * 0.9
        return (
            f'<rect class="{cls}" x="{_num(x - s)}" y="{_num(y - s)}" '
            f'width="{_num(2 * s)}" height="{_num(2 * s)}"/>'
        )
    if symbol == "diamond":
        d = r * 1.25
        points = [(x, y - d), (x + d, y), (x, y + d), (x - d, y)]
    elif symbol == "triangle-up":
        d = r * 1.2
        points = [(x, y - d), (x + d, y + d * 0.8), (x - d, y + d * 0.8)]
    elif symbol == "star":
        points = []
        for k in range(10):
            radius = r * 1.3 if k % 2 == 0 else r * 0.55
            angle = math.pi / 2 + k * math.pi / 5
            points.append((x + radius * math.cos(angle), y - radius * math.sin(angle)))
    elif symbol == "x":
        d, w = r, r * 0.35
        # An "x" made of two thick bars, drawn as one filled outline.
        return (
            f'<path class="{cls}" d="M{_num(x - d)},{_num(y - d + w)}L{_num(x - d + w)},'
            f"{_num(y - d)}L{_num(x + d)},{_num(y + d - w)}L{_num(x + d - w)},{_num(y + d)}Z"
            f"M{_num(x + d - w)},{_num(y - d)}L{_num(x + d)},{_num(y - d + w)}L{_num(x - d + w)},"
            f'{_num(y + d)}L{_num(x - d)},{_num(y + d - w)}Z"/>'
        )
    else:
        return f'<circle class="{cls}" cx="{_num(x)}" cy="{_num(y)}" r="{_num(r)}"/>'
    coords = "L".join(f"{_num(px)},{_num(py)}" for px, py in points)
    return f'<path class="{cls}" d="M{coords}Z"/>'


def _symbols(doc: Mapping[str, Any], n: int) -> list[str]:
    traces = doc.get("plotly", {}).get("data", [])
    out = []
    for j in range(n):
        try:
            out.append(str(traces[j]["marker"]["symbol"]))
        except (IndexError, KeyError, TypeError):
            out.append("circle")
    return out


def _value_label(doc: Mapping[str, Any]) -> str:
    try:
        return str(doc["plotly"]["layout"]["xaxis"]["title"]["text"])
    except (KeyError, TypeError):
        return ""


def render_dot_svg(doc: Mapping[str, Any]) -> str:
    """The dot plot as one ``<svg>`` element (aria-hidden, sized by its viewBox)."""
    data = doc["data"]
    categories: Sequence[str] = data["categories"]
    series: Sequence[Mapping[str, Any]] = data["series"]
    if not categories or not series:
        raise ValueError("a dot plot needs at least one category and one series")
    decimals = int(data.get("decimals", 1))
    suffix = "%" if data.get("unit") == "percent" else ""
    symbols = _symbols(doc, len(series))

    highs = [v for s in series for v in (s.get("upper") or s["values"]) if v is not None]
    top, step = nice_max(max(highs))

    def sx(value: float) -> float:
        return PLOT_LEFT + (PLOT_RIGHT - PLOT_LEFT) * max(0.0, min(value, top)) / top

    row_h = LABEL_H + SERIES_GAP * len(series) + ROW_PAD
    plot_h = row_h * len(categories)
    height = plot_h + AXIS_H
    parts: list[str] = []

    # Vertical grid lines and tick labels.
    n_ticks = round(top / step)
    for k in range(n_ticks + 1):
        value = k * step
        x = sx(value)
        parts.append(f'<line class="dot-grid" x1="{_num(x)}" y1="0" x2="{_num(x)}" y2="{plot_h}"/>')
        anchor = "start" if k == 0 else "middle"
        tick = _fmt(value, 0 if float(value).is_integer() else 1)
        parts.append(
            f'<text class="dot-text" x="{_num(x)}" y="{plot_h + 18}" '
            f'text-anchor="{anchor}">{tick}{suffix}</text>'
        )
    label = _value_label(doc)
    if label:
        parts.append(
            f'<text class="dot-text" x="{_num((PLOT_LEFT + PLOT_RIGHT) / 2)}" '
            f'y="{plot_h + 42}" text-anchor="middle">{html.escape(label)}</text>'
        )

    for i, category in enumerate(categories):
        y0 = i * row_h
        parts.append(
            f'<text class="dot-text dot-cat" x="{PLOT_LEFT}" y="{y0 + 16}">'
            f"{html.escape(category)}</text>"
        )
        for j, s in enumerate(series):
            value = s["values"][i]
            y = y0 + LABEL_H + SERIES_GAP * j + SERIES_GAP / 2
            cls = f"dot-s{j}"
            right = sx(value)
            lower, upper = s.get("lower"), s.get("upper")
            if lower is not None and upper is not None:
                lo, hi = sx(lower[i]), sx(upper[i])
                right = hi
                parts.append(
                    f'<path class="{cls} dot-whisker" d="M{_num(lo)},{_num(y)}H{_num(hi)}'
                    f"M{_num(lo)},{_num(y - 5)}V{_num(y + 5)}M{_num(hi)},{_num(y - 5)}"
                    f'V{_num(y + 5)}"/>'
                )
            parts.append(marker(symbols[j], sx(value), y, f"{cls} dot-mark"))
            parts.append(
                f'<text class="dot-text dot-value" x="{_num(max(right, sx(value) + MARKER) + 6)}" '
                f'y="{_num(y + 5)}">{html.escape(label_text(value, decimals))}{suffix}</text>'
            )

    body = "".join(parts)
    return (
        f'<svg class="dot-svg" viewBox="0 0 {WIDTH} {height}" aria-hidden="true" '
        f'focusable="false" xmlns="http://www.w3.org/2000/svg">{body}</svg>'
    )


def legend_html(doc: Mapping[str, Any]) -> str:
    """The series key, each name with its marker shape (shown only when there are 2+ series)."""
    series = doc["data"]["series"]
    if len(series) < 2:
        return ""
    symbols = _symbols(doc, len(series))
    items = []
    for j, s in enumerate(series):
        shape = marker(symbols[j], 9, 9, f"dot-s{j} dot-mark")
        items.append(
            f'<li><svg class="dot-key" viewBox="0 0 18 18" aria-hidden="true" '
            f'focusable="false">{shape}</svg>{html.escape(s["name"])}</li>'
        )
    return f'<ul class="dot-legend" aria-hidden="true">{"".join(items)}</ul>'


def theme_css(doc: Mapping[str, Any], selector: str = ".dot-chart") -> str:
    """CSS custom properties for the chart from the document's light and dark themes."""

    def props(theme: Mapping[str, Any]) -> str:
        n = len(doc["data"]["series"])
        colours = [f"--dot-s{j}:{theme['series'][j]}" for j in range(n)]
        return ";".join([*colours, f"--dot-grid:{theme['grid']}", f"--dot-text:{theme['text']}"])

    themes = doc["themes"]
    light = f"{selector}{{{props(themes['light'])}}}"
    if "dark" not in themes:
        return light
    dark = f"{selector}{{{props(themes['dark'])}}}"
    return f"{light}@media (prefers-color-scheme: dark){{{dark}}}"
