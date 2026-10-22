"""DEPRECATED: the P1 stop-gap API, kept as thin wrappers over the 0.1 API.

Use :func:`disability_access_charts.bar`, :func:`~disability_access_charts.describe`,
:func:`~disability_access_charts.check_alt_text` and
:func:`~disability_access_charts.audit` instead. Every function here keeps its old
signature and return type and issues a ``DeprecationWarning``. The module will be removed
in a later release.
"""

from __future__ import annotations

import warnings
from collections.abc import Mapping, Sequence
from typing import Any

from disability_access_charts.audit import alt_text_checks, theme_checks
from disability_access_charts.describe import (
    ChartData,
    Series,
    describe,
    format_number,
    format_percent,
)
from disability_access_charts.describe import check_alt_text as _check_alt_text
from disability_access_charts.palettes import DEFAULT_THEMES, Theme
from disability_access_charts.plots import bar

__all__ = [
    "DEFAULT_THEMES",
    "Theme",
    "audit_chart",
    "bar_chart",
    "check_alt_text",
    "describe_bar_chart",
    "format_number",
    "format_percent",
]


def _deprecated(old: str, new: str) -> None:
    warnings.warn(
        f"disability_access_charts.experimental.{old} is deprecated; use {new}",
        DeprecationWarning,
        stacklevel=3,
    )


def _counts(
    categories: Sequence[str],
    values: Sequence[float],
    *,
    verbatim: Sequence[str] = (),
    category_label: str = "Category",
) -> ChartData:
    return ChartData(
        categories=tuple(categories),
        series=(Series("value", tuple(values)),),
        unit="count",
        decimals=0,
        shares=True,
        verbatim=tuple(verbatim),
        category_label=category_label,
    )


def describe_bar_chart(
    categories: Sequence[str],
    values: Sequence[float],
    *,
    title: str,
    category_label: str,
    source: str,
) -> str:
    """Alt-text for a bar chart of counts, built only from the data passed in."""
    _deprecated("describe_bar_chart", "disability_access_charts.describe")
    data = _counts(categories, values, verbatim=(title, source), category_label=category_label)
    return describe(data, chart_type="bar", title=title, source=source)


def check_alt_text(
    alt_text: str,
    categories: Sequence[str],
    values: Sequence[float],
    *,
    verbatim: Sequence[str] = (),
) -> list[str]:
    """Return the numbers in ``alt_text`` that do not check out against the data.

    The 0.1 checker also checks which category each number belongs to and the claims
    made; this wrapper returns only the numbers it rejects, as before.
    """
    _deprecated("check_alt_text", "disability_access_charts.check_alt_text")
    data = _counts(categories, values, verbatim=verbatim)
    return [
        p.number
        for p in _check_alt_text(alt_text, data)
        if p.severity == "error" and p.number is not None
    ]


def audit_chart(
    themes: Mapping[str, Theme],
    alt_text: str,
    categories: Sequence[str],
    values: Sequence[float],
    *,
    verbatim: Sequence[str] = (),
) -> dict[str, Any]:
    """Contrast checks for every theme, plus the alt-text check."""
    _deprecated("audit_chart", "disability_access_charts.audit")
    checks = theme_checks(themes, chart_type="bar", n_series=1)
    checks += alt_text_checks(alt_text, _counts(categories, values, verbatim=verbatim))
    errors = [c for c in checks if c["severity"] == "error"]
    return {"passed": all(c["passed"] for c in errors), "checks": checks}


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
    """A horizontal bar-chart document of counts; see :func:`disability_access_charts.bar`."""
    _deprecated("bar_chart", "disability_access_charts.bar")
    doc = bar(
        categories,
        values,
        title=title,
        value_label=value_label,
        category_label=category_label,
        source=source,
        themes=themes,
        chart_id=chart_id,
    )
    doc["meta"]["experimental"] = True
    return doc
