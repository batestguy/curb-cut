"""Charts that check their own words.

Accessible Plotly charts whose alt-text is built from the data and checked against it
(numbers and comparative claims), with an audit you can run in CI and a data-table
fallback for every chart. Built for Curb Cut, an accessible platform for Nigerian
disability data.

New in 0.2: statistical findings with false discovery rate control
(:func:`statistical_findings`, ``findings=True`` on the chart builders), adire-inspired
pattern fills (:mod:`~disability_access_charts.patterns`, :func:`grouped_bar`), and stable
map support (:func:`choropleth`).
"""

from disability_access_charts._version import __version__
from disability_access_charts.audit import audit
from disability_access_charts.contrast import (
    contrast_ratio,
    passes_non_text,
    passes_text,
    relative_luminance,
)
from disability_access_charts.describe import (
    ChartData,
    Problem,
    Series,
    check_alt_text,
    describe,
)
from disability_access_charts.findings import Reference, statistical_findings
from disability_access_charts.maps import MAP_THEMES, MapTheme, choropleth
from disability_access_charts.palettes import DEFAULT_THEMES, OKABE_ITO, SYMBOLS, Theme
from disability_access_charts.patterns import PATTERNS, Pattern
from disability_access_charts.plots import bar, dot, figure, grouped_bar
from disability_access_charts.table import to_csv, to_html
from disability_access_charts.theme import theme

__all__ = [
    "DEFAULT_THEMES",
    "MAP_THEMES",
    "OKABE_ITO",
    "PATTERNS",
    "SYMBOLS",
    "ChartData",
    "MapTheme",
    "Pattern",
    "Problem",
    "Reference",
    "Series",
    "Theme",
    "__version__",
    "audit",
    "bar",
    "check_alt_text",
    "choropleth",
    "contrast_ratio",
    "describe",
    "dot",
    "figure",
    "grouped_bar",
    "passes_non_text",
    "passes_text",
    "relative_luminance",
    "statistical_findings",
    "theme",
    "to_csv",
    "to_html",
]
