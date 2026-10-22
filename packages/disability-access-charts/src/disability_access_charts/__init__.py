"""Charts that check their own words.

Accessible Plotly charts whose alt-text is built from the data and checked against it
(numbers and comparative claims), with an audit you can run in CI and a data-table
fallback for every chart. Built for Curb Cut, an accessible platform for Nigerian
disability data.
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
from disability_access_charts.palettes import DEFAULT_THEMES, OKABE_ITO, SYMBOLS, Theme
from disability_access_charts.plots import bar, dot, figure
from disability_access_charts.table import to_csv, to_html
from disability_access_charts.theme import theme

__all__ = [
    "DEFAULT_THEMES",
    "OKABE_ITO",
    "SYMBOLS",
    "ChartData",
    "Problem",
    "Series",
    "Theme",
    "__version__",
    "audit",
    "bar",
    "check_alt_text",
    "contrast_ratio",
    "describe",
    "dot",
    "figure",
    "passes_non_text",
    "passes_text",
    "relative_luminance",
    "theme",
    "to_csv",
    "to_html",
]
