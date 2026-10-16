"""Accessible charts: alt-text checked against the data, a CI-ready audit,
and a data-table fallback for every chart.

Early release: only the WCAG contrast checks exist so far.
"""

from disability_access_charts.contrast import (
    contrast_ratio,
    passes_non_text,
    passes_text,
    relative_luminance,
)

__version__ = "0.0.1"

__all__ = ["contrast_ratio", "passes_non_text", "passes_text", "relative_luminance"]
