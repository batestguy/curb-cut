"""Apply a colour theme to a chart document or a Plotly figure."""

from __future__ import annotations

import copy
from collections.abc import Mapping
from typing import Any

from disability_access_charts.palettes import DEFAULT_THEMES, Theme


def _apply(fig: dict[str, Any], t: Theme, *, chart_type: str | None = None) -> dict[str, Any]:
    layout = fig.setdefault("layout", {})
    layout["paper_bgcolor"] = t.background
    layout["plot_bgcolor"] = t.background
    layout["font"] = {**(layout.get("font") or {}), "color": t.text}
    for key in [k for k in layout if k.startswith(("xaxis", "yaxis"))] or ["xaxis", "yaxis"]:
        axis = layout.setdefault(key, {})
        axis["gridcolor"] = t.grid
        axis["tickfont"] = {**(axis.get("tickfont") or {}), "color": t.text}
        title = axis.get("title")
        if isinstance(title, Mapping):
            axis["title"] = {**title, "font": {**(title.get("font") or {}), "color": t.text}}
    if "legend" in layout or layout.get("showlegend"):
        legend = layout.setdefault("legend", {})
        legend["font"] = {**(legend.get("font") or {}), "color": t.text}
    scatter_index = 0
    for trace in fig.get("data") or []:
        kind = trace.get("type", "scatter")
        marker = trace.setdefault("marker", {})
        if kind == "bar" and chart_type != "dot":
            marker["color"] = t.mark
        elif t.series:
            marker["color"] = t.series[scatter_index % len(t.series)]
            scatter_index += 1
        # Dot-plot whiskers follow their series' colour; bar whiskers take the text colour.
        whisker = marker["color"] if chart_type == "dot" and t.series else t.text
        for bars in ("error_x", "error_y"):
            if isinstance(trace.get(bars), Mapping):
                trace[bars] = {**trace[bars], "color": whisker}
        trace["textfont"] = {**(trace.get("textfont") or {}), "color": t.text}
    return fig


def theme(fig: Any, name: str | Theme = "light", themes: Mapping[str, Theme] | None = None) -> Any:
    """A themed copy of ``fig``; the input is not changed.

    ``fig`` is a chart document (its ``plotly`` part is themed), a Plotly figure dict, or a
    Plotly ``Figure`` (a new figure of the same type is returned). ``name`` picks a theme
    from ``themes`` (default :data:`~disability_access_charts.palettes.DEFAULT_THEMES`), or
    is a :class:`~disability_access_charts.palettes.Theme` itself.
    """
    t = name if isinstance(name, Theme) else dict(themes or DEFAULT_THEMES)[name]
    if isinstance(fig, Mapping) and "plotly" in fig and "themes" in fig:
        doc = copy.deepcopy(dict(fig))
        chart_type = (doc.get("meta") or {}).get("chart_type")
        doc["plotly"] = _apply(doc["plotly"], t, chart_type=chart_type)
        return doc
    if isinstance(fig, Mapping):
        return _apply(copy.deepcopy(dict(fig)), t)
    for method in ("to_plotly_json", "to_dict"):
        if callable(getattr(fig, method, None)):
            return type(fig)(_apply(copy.deepcopy(getattr(fig, method)()), t))
    raise TypeError(f"cannot theme a {type(fig).__name__}")
