"""EXPERIMENTAL: build-time chart documents for static sites.

This module is a stop-gap for Curb Cut's P1 slice and is **not a stable API**. It will
change or disappear when the real plotting API lands in 0.1. It is not exported from the
package root.

:func:`bar_chart` returns one JSON-serialisable document holding everything a page needs
to show a chart accessibly, with no Plotly import (the figure is plain dicts):

* ``plotly`` -- a Plotly.js figure spec (``data`` + ``layout``), static, no hover-only data;
* ``themes`` -- light and dark colour sets for the page to apply;
* ``alt_text`` -- a description derived from the data, never written by hand;
* ``table`` -- the same data as an HTML-ready table (caption, columns, rows);
* ``audit`` -- WCAG contrast checks for every theme, plus a check that every number in
  the alt-text can be recomputed from the table;
* ``meta`` -- provenance.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from typing import Any

from disability_access_charts.contrast import (
    NON_TEXT_MIN,
    TEXT_MIN,
    contrast_ratio,
)

_NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")


@dataclass(frozen=True)
class Theme:
    """Colours for one colour scheme.

    ``mark`` is the bar fill. ``highlight`` (optional) is the fill for one selected bar; it
    must differ from both the background and ``mark`` by at least 3:1, and a page that uses
    it should add a non-colour cue too (an outline, a bold label).
    """

    background: str
    text: str
    mark: str
    grid: str
    highlight: str | None = None


# Nigerian flag green. Light: the flag green #008751 on white (about 4.6:1), with a deep
# indigo highlight (about 3.5:1 against the green). Dark: with light green bars, the only
# colours 3:1 from both them and the background are dim mid-tones (a crimson such as
# #c31e55, about 3.2:1), which read as "darker", not "selected". So the bars are a mid green
# (about 4.1:1 on near-black) and the highlight is a light gold (about 3.5:1 against them).
DEFAULT_THEMES: dict[str, Theme] = {
    "light": Theme(
        background="#ffffff", text="#1a1a1a", mark="#008751", grid="#d9d9d9", highlight="#1b1464"
    ),
    "dark": Theme(
        background="#121212", text="#f0f0f0", mark="#198754", grid="#3a3a3a", highlight="#ffe08a"
    ),
}


def format_number(value: float) -> str:
    """Thousands separators; integers stay integers."""
    if float(value).is_integer():
        return f"{int(value):,}"
    return f"{value:,.1f}"


def format_percent(value: float) -> str:
    return f"{value:.1f}"


def _shares(values: Sequence[float]) -> list[float]:
    total = sum(values)
    if total <= 0:
        raise ValueError("values must sum to a positive total")
    return [100 * v / total for v in values]


def _names(categories: Sequence[str], indices: list[int]) -> str:
    names = [categories[i] for i in indices]
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]


def describe_bar_chart(
    categories: Sequence[str],
    values: Sequence[float],
    *,
    title: str,
    category_label: str,
    source: str,
) -> str:
    """Alt-text for a bar chart, built only from the data passed in."""
    shares = _shares(values)
    hi, lo = max(values), min(values)
    largest = [i for i, v in enumerate(values) if v == hi]
    smallest = [i for i, v in enumerate(values) if v == lo]

    def clause(indices: list[int]) -> str:
        each = "each " if len(indices) > 1 else ""
        i = indices[0]
        return (
            f"{_names(categories, indices)}, {each}{format_number(values[i])} "
            f"({format_percent(shares[i])}% of the total)"
        )

    return (
        f"Bar chart: {title}. {len(categories)} bars, one per {category_label.lower()}. "
        f"Largest: {clause(largest)}. Smallest: {clause(smallest)}. "
        f"Total: {format_number(sum(values))}. Source: {source}."
    )


def check_alt_text(
    alt_text: str,
    categories: Sequence[str],
    values: Sequence[float],
    *,
    verbatim: Sequence[str] = (),
) -> list[str]:
    """Return the numbers in ``alt_text`` that cannot be recomputed from the data.

    Strings in ``verbatim`` (the title, the source) are removed first, since numbers in
    them (a year, say) are quoted rather than computed. An empty list means every number
    in the alt-text checks out.
    """
    text = alt_text
    for fixed in verbatim:
        text = text.replace(fixed, " ")
    shares = _shares(values)
    allowed = {format_number(len(categories)), format_number(sum(values))}
    allowed |= {format_number(v) for v in values}
    allowed |= {format_percent(s) for s in shares}
    return [token for token in _NUMBER.findall(text) if token not in allowed]


def _contrast_check(
    criterion: str,
    theme: str,
    what: str,
    foreground: str,
    background: str,
    minimum: float,
    *,
    against: str = "background",
) -> dict[str, Any]:
    ratio = contrast_ratio(foreground, background)
    return {
        "id": f"wcag-{criterion}",
        "theme": theme,
        "description": f"{what} against {against}",
        "foreground": foreground,
        "background": background,
        "ratio": round(ratio, 2),
        "minimum": minimum,
        "passed": ratio >= minimum,
    }


def audit_chart(
    themes: Mapping[str, Theme],
    alt_text: str,
    categories: Sequence[str],
    values: Sequence[float],
    *,
    verbatim: Sequence[str] = (),
) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    for name, theme in themes.items():
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
    unverified = check_alt_text(alt_text, categories, values, verbatim=verbatim)
    checks.append(
        {
            "id": "alt-text-matches-data",
            "description": "Every number in the alt-text is recomputed from the data",
            "unverified_numbers": unverified,
            "passed": not unverified,
        }
    )
    return {"passed": all(c["passed"] for c in checks), "checks": checks}


def bar_chart(
    categories: Sequence[str],
    values: Sequence[float],
    *,
    title: str,
    value_label: str,
    category_label: str,
    source: str,
    themes: Mapping[str, Theme] | None = None,
    chart_id: str = "chart",
) -> dict[str, Any]:
    """EXPERIMENTAL. Build a horizontal bar-chart document (see the module docstring).

    Bars are drawn in the order given, top to bottom.
    """
    if len(categories) != len(values) or not categories:
        raise ValueError("categories and values must be non-empty and the same length")
    if any(v < 0 for v in values):
        raise ValueError("values must be non-negative")
    themes = dict(themes or DEFAULT_THEMES)
    if "light" not in themes:
        raise ValueError("a 'light' theme is required; it is the default rendering")
    light = themes["light"]
    shares = _shares(values)
    alt_text = describe_bar_chart(
        categories, values, title=title, category_label=category_label, source=source
    )

    axis_font = {"color": light.text, "size": 14}
    plotly = {
        "data": [
            {
                "type": "bar",
                "orientation": "h",
                "x": list(values),
                "y": list(categories),
                "marker": {"color": light.mark},
                "text": [format_number(v) for v in values],
                "textposition": "outside",
                "cliponaxis": False,
                "hoverinfo": "skip",
            }
        ],
        "layout": {
            "title": {"text": ""},  # the page's <figcaption> carries the title
            "paper_bgcolor": light.background,
            "plot_bgcolor": light.background,
            "font": {"color": light.text, "size": 14},
            "margin": {"l": 10, "r": 90, "t": 10, "b": 60},
            "xaxis": {
                "title": {"text": value_label, "font": axis_font},
                "tickformat": ",~s",
                "gridcolor": light.grid,
                "zeroline": False,
                "fixedrange": True,
            },
            "yaxis": {"autorange": "reversed", "automargin": True, "fixedrange": True},
            "showlegend": False,
            "bargap": 0.25,
        },
    }
    table = {
        "caption": f"{title}. Source: {source}.",
        "columns": [
            {"key": "category", "label": category_label, "type": "text"},
            {"key": "value", "label": value_label, "type": "integer"},
            {"key": "share", "label": "Share of total (%)", "type": "percent"},
        ],
        "rows": [[c, v, round(s, 1)] for c, v, s in zip(categories, values, shares, strict=True)],
        "total": sum(values),
    }
    return {
        "id": chart_id,
        "title": title,
        "plotly": plotly,
        "themes": {name: asdict(t) for name, t in themes.items()},
        "alt_text": alt_text,
        "table": table,
        "audit": audit_chart(themes, alt_text, categories, values, verbatim=(title, source)),
        "meta": {
            "experimental": True,
            "generator": "disability_access_charts.experimental.bar_chart",
            "chart_type": "bar",
            "source": source,
        },
    }
