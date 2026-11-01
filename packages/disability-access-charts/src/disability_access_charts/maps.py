"""A choropleth (shaded map) document. Stable API since 0.2.

``from disability_access_charts import choropleth`` (or from this module). Documents carry
``meta.chart_type = "choropleth"``, and :func:`disability_access_charts.audit.audit` (and so
the ``check`` CLI) audits them with :func:`map_checks`. In 0.1 this was experimental
(``meta.experimental = True``); its arguments are unchanged.

A choropleth document follows the bar and dot documents: one JSON-serialisable dict with
the map geometry (SVG paths the page draws itself; no Plotly), light and dark themes, the
classes, alt-text built from the data and checked against it, a data table, keyboard
metadata, an audit and provenance.

Classes and colour
------------------
Values are put in **fixed classes** given by their breaks (``breaks=[2, 3, 4, 6]`` gives
"Under 2%", "2% to under 3%", ..., "6% and over"). Each value is classed **as displayed**,
rounded to ``decimals``, so a state shown as 2.0% is never in "Under 2%".

A sequential colour scale of five steps cannot give 3:1 contrast between every pair of
neighbouring classes (WCAG 2.2 SC 1.4.11 asks 3:1 for graphics needed to understand the
content): from white to the darkest green that still meets 3:1 against the boundaries there
is room for about one 3:1 step, not four. So colour is never the only way to read the map
(SC 1.4.1), and the audit checks each of these:

* every state boundary is drawn in the theme's ``edge`` colour, at least 3:1 against the
  page background **and** against every class fill, so each state's shape is visible
  whatever its class; the legend swatches are outlined in the same colour;
* the legend states each class's range in words, with the number of states in it;
* the data table holds every state's value, interval and class;
* the page shows a tooltip on hover, tap and keyboard focus (the page's job; the document
  records ``keyboard.tooltip``).

The ratios between neighbouring class fills are reported in the audit's
``not-colour-alone`` check, so the trade-off is visible, not hidden. The fills get darker
(light theme) or brighter (dark theme) with the value, and the audit checks that order.

Patterns (new in 0.2, on by default for up to five classes)
-----------------------------------------------------------
Each class also gets its own pattern tile (:mod:`disability_access_charts.patterns`), drawn
over its fill as an SVG ``<pattern>``, from the sparsest ink (lowest class) to the densest.
Neighbouring classes then differ by a pattern as well as a shade. The document's
``patterns`` block holds the tiles, each theme's ink and the tile scale in map units, and
each class names its tile (``classes[k]["pattern"]``) for the legend. The audit checks that
classes and patterns line up one to one, that the ink is 3:1 against every fill in every
theme, and that the legend has each class's pattern.

``patterns=None`` (the default) means "auto": patterns are on with five classes or fewer,
and off with more (there are five tiles). ``patterns=True`` with more than five classes
raises; ``patterns=False`` gives the 0.1 document. Without patterns, the audit adds a
``shade-alone`` **warning** that neighbouring classes differ by shade alone, so a map
that falls back to the 0.1 document is never silent about it.

Schemes, casing, per-class ink and colour vision (new in 0.3)
-------------------------------------------------------------
``scheme`` names a set of light and dark themes (:data:`MAP_SCHEMES`). The default,
``"ylgnbu"``, runs yellow to green to blue (ColorBrewer's five-class YlGnBu in the light
theme; a matching dark palette, brighter for higher values) with larger lightness steps than
0.2's greens. ``scheme="green"`` gives exactly the 0.2 look: the 0.2 greens, one boundary
colour, the 0.2 pattern order and one ink per theme.

* **Casing.** No single boundary colour is 3:1 against both a near-white and a dark blue
  fill, so a theme can add a ``halo``: the page draws every boundary twice, a wide stroke in
  the ``halo`` colour under a narrow one in the ``edge`` colour (dark on light in the light
  theme, light on dark in the dark theme), so at every border one of the two stands out.
  The audit asks that the edge is 3:1 against the background and against the halo, and that
  for the background and for every fill at least one of edge and halo is 3:1. A theme with
  no halo keeps the 0.2 rule (edge 3:1 against the background and every fill).
* **Pattern order.** In the 0.3 schemes classes take :data:`~disability_access_charts.
  patterns.MAP_PATTERNS`, ordered by ink weight (plain, dots, lines, crosshatch, solid), and
  **each class has its own ink**, black or white, whichever contrasts more with its fill
  (``patterns.class_ink``); the audit checks each at 3:1 (classes with no ink are exempt).
* **Colour vision.** The ``colour-vision`` check simulates deuteranopia, protanopia and
  tritanopia (Machado et al. 2009, severity 1.0) and asks that neighbouring fills are at
  least :data:`~disability_access_charts.vision.CVD_MIN_DELTA_E` apart in CIEDE2000 in
  every simulation (error); ``colour-vision-target`` warns below
  :data:`~disability_access_charts.vision.CVD_TARGET_DELTA_E`
  (:mod:`disability_access_charts.vision`).
* **Legend filter.** With ``legend_filter=True`` (the default) each class lists its regions
  and the sentence a page announces when a legend button shows only that class
  (``classes[k]["announce"]``, ``legend.announce_all``); the audit checks them against the
  data.
"""

from __future__ import annotations

import itertools
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from typing import Any

from disability_access_charts import _lang
from disability_access_charts._version import __version__
from disability_access_charts.contrast import (
    NON_TEXT_MIN,
    TEXT_MIN,
    contrast_ratio,
    relative_luminance,
)
from disability_access_charts.describe import DEFAULT_INTERVAL_LABEL, ChartData, Series, describe
from disability_access_charts.patterns import (
    PATTERNS,
    assign,
    assign_map,
    class_inks,
    ink_for,
    pattern_checks,
    tile_dict,
)
from disability_access_charts.vision import (
    CVD_MIN_DELTA_E,
    CVD_TARGET_DELTA_E,
    SIMULATIONS,
    neighbour_differences,
)

SCHEMA = "1.1"
"""Changed in 0.3 (from "1.0"): themes may carry a ``halo``; ``patterns.class_ink``;
``patterns.sequence``; each class's ``regions`` and ``announce``; ``legend``;
``keyboard.legend_filter``; ``meta.scheme``."""


@dataclass(frozen=True)
class MapTheme:
    """Colours for one colour scheme of a choropleth.

    ``classes`` are the fills, lowest class first. ``edge`` draws every boundary and outlines
    the legend swatches. Without a ``halo`` (0.2), the edge must be 3:1 against
    ``background`` and against every fill. With one (new in 0.3), every boundary is cased:
    a wide ``halo`` stroke under a narrow ``edge`` stroke; the edge must be 3:1 against the
    background and the halo, and one of the two 3:1 against the background and every fill.
    """

    background: str
    text: str
    edge: str
    classes: tuple[str, ...]
    halo: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """As a document stores it; ``halo`` only when there is one (so 0.2 themes are
        unchanged)."""
        out = asdict(self)
        if self.halo is None:
            del out["halo"]
        return out


DEFAULT_SCHEME = "ylgnbu"

# "ylgnbu" (the default since 0.3). Light: ColorBrewer's five-class YlGnBu (Brewer,
# colorbrewer2.org), near-black edges on white halos. Dark: drawn for this library to match:
# yellow (olive) to green to teal to blue to a pale blue, brighter for higher values, the
# darkest still 1.9:1 and a CIEDE2000 of 17.8 or more from the background in every
# simulated colour vision; white edges on near-black halos. Neighbouring fills are at least
# 10.3 (light) and 11.6 (dark) apart in CIEDE2000 under normal vision, deuteranopia,
# protanopia and tritanopia.
#
# "green" (the 0.2 look). Five greens around the site's flag green. Light: from a pale green
# to the brand mark #008751, with near-black boundaries (3.8:1 against #008751, 15:1 against
# the palest). Dark: from a green just above the background to a mid green, with white
# boundaries (3.3:1 against the brightest fill). Neighbouring fills differ by 1.3-1.6:1, and
# by 7.5 to 8.2 in CIEDE2000 at their closest under simulated colour-vision deficiency.
MAP_SCHEMES: dict[str, dict[str, MapTheme]] = {
    "ylgnbu": {
        "light": MapTheme(
            background="#ffffff",
            text="#1a1a1a",
            edge="#1a1a1a",
            halo="#ffffff",
            classes=("#ffffcc", "#a1dab4", "#41b6c4", "#2c7fb8", "#253494"),
        ),
        "dark": MapTheme(
            background="#121212",
            text="#f0f0f0",
            edge="#ffffff",
            halo="#121212",
            classes=("#4a4512", "#2b7340", "#1b8f96", "#77bdf2", "#d4ebff"),
        ),
    },
    "green": {
        "light": MapTheme(
            background="#ffffff",
            text="#1a1a1a",
            edge="#1a1a1a",
            classes=("#e4f3e9", "#b5dec3", "#7dc39a", "#3fa16f", "#008751"),
        ),
        "dark": MapTheme(
            background="#121212",
            text="#f0f0f0",
            edge="#ffffff",
            classes=("#1b2f23", "#1e4b33", "#226943", "#2a8753", "#34a061"),
        ),
    },
}
"""Named colour schemes for :func:`choropleth`, each with a light and a dark theme."""

MAP_THEMES: dict[str, MapTheme] = MAP_SCHEMES[DEFAULT_SCHEME]
"""The default scheme's themes. **Changed in 0.3:** YlGnBu with cased boundaries (it was
the greens, now ``MAP_SCHEMES["green"]``)."""


def _number(value: float) -> str:
    """A break as written in a class label: no trailing zeros ("2", "2.5")."""
    return f"{value:,.6f}".rstrip("0").rstrip(".")


def class_labels(breaks: Sequence[float], unit: str) -> list[str]:
    """'Under 2%', '2% to under 3%', ..., '6% and over'."""
    suffix = "%" if unit == "percent" else ""
    b = [f"{_number(x)}{suffix}" for x in breaks]
    labels = [f"Under {b[0]}"]
    labels += [f"{lo} to under {hi}" for lo, hi in itertools.pairwise(b)]
    labels.append(f"{b[-1]} and over")
    return labels


def classify(value: float, breaks: Sequence[float], decimals: int) -> int:
    """The class index of ``value`` as displayed (rounded to ``decimals``)."""
    shown = round(value, decimals)
    return sum(1 for b in breaks if shown >= b)


def _class_sentence(classes: Sequence[Mapping[str, Any]], label: str) -> str:
    items = "; ".join(
        f"{c['label'].lower() if i == 0 else c['label']}, {c['count']} "
        f"{label if c['count'] == 1 else label + 's'}"
        for i, c in enumerate(classes)
    )
    return f"Shaded in {len(classes)} classes: {items}."


def _announcements(
    classes: Sequence[Mapping[str, Any]],
    regions: Sequence[Sequence[str]],
    *,
    label: str,
    lang: str,
) -> tuple[list[str], str]:
    """What a page announces when a legend button shows one class (one sentence per class),
    and when it shows all classes again."""
    t = _lang.get(lang).MAP_LEGEND
    sentences = []
    for k, (c, names) in enumerate(zip(classes, regions, strict=True)):
        n = len(names)
        rng = c["label"].lower() if k == 0 else c["label"]
        noun = label if n == 1 else label + "s"
        if n == 0:
            sentences.append(t["filter_empty"].format(plural=label + "s", range=rng))
        else:
            joined = t["names_separator"].join(names)
            sentences.append(t["filter_class"].format(n=n, noun=noun, range=rng, names=joined))
    total = sum(len(names) for names in regions)
    everything = t["filter_all"].format(n=total, noun=label if total == 1 else label + "s")
    return sentences, everything


def _intro(title: str, n: int, label: str, interval: str | None) -> str:
    noun = label if n == 1 else label + "s"
    if interval:
        return f"Map: {title}. {n} {noun}, each with its {interval}."
    return f"Map: {title}. {n} {noun}."


def _alt_text(
    data: ChartData,
    classes: Sequence[Mapping[str, Any]],
    *,
    title: str,
    source: str,
    lang: str,
) -> tuple[str, str, str]:
    """(full alt-text, its class sentence, the rest the claim checker reads)."""
    language = _lang.get(lang)
    label = language.label(data.category_label)
    series = data.series[0]
    interval = data.interval_label if series.has_interval else None
    # The dot-plot description of the same data, after its own introduction: the extremes,
    # whether the survey can tell them from the next estimate, and their intervals.
    dots = describe(data, chart_type="dot", title=title, source=source, lang=lang)
    t = language.TEMPLATES
    key = "intro_dots_ci" if series.has_interval else "intro_dots"
    n = len(data.categories)
    dot_intro = t[key].format(
        kind=t["kind_dot"], title=title, n=n, label=label, interval=data.interval_label
    )
    if not dots.startswith(dot_intro + " "):
        raise AssertionError("unexpected dot-plot introduction")  # pragma: no cover
    dots = dots[len(dot_intro) + 1 :]
    intro = _intro(title, n, label, interval)
    sentence = _class_sentence(classes, label)
    checked = f"{intro} {dots}"
    return f"{intro} {sentence} {dots}", sentence, checked


def _table(
    data: ChartData,
    names: Sequence[str],
    class_index: Sequence[int],
    labels: Sequence[str],
    extra_columns: Sequence[tuple[str, Sequence[str]]],
    *,
    title: str,
    source: str,
    value_label: str,
) -> dict[str, Any]:
    series = data.series[0]
    number = {"type": "number", "decimals": data.decimals}
    columns: list[dict[str, Any]] = [
        {"key": "category", "label": data.category_label, "type": "text"},
        {"key": "value", "label": value_label, **number},
    ]
    if series.has_interval:
        for bound in ("lower", "upper"):
            columns.append({"key": bound, "label": f"{data.interval_label}, {bound}", **number})
    columns.append({"key": "class", "label": "Map class", "type": "text"})
    columns += [
        {"key": f"extra:{i}", "label": label, "type": "text"}
        for i, (label, _) in enumerate(extra_columns)
    ]
    order = sorted(range(len(names)), key=lambda i: names[i])
    rows = []
    for i in order:
        row: list[Any] = [names[i], series.values[i]]
        if series.lower is not None and series.upper is not None:
            row += [series.lower[i], series.upper[i]]
        row.append(labels[class_index[i]])
        row += [values[i] for _, values in extra_columns]
        rows.append(row)
    return {"caption": f"{title}. Source: {source}.", "columns": columns, "rows": rows}


def choropleth(
    names: Sequence[str],
    codes: Sequence[str],
    values: Sequence[float],
    *,
    paths: Mapping[str, str],
    view_box: str,
    breaks: Sequence[float],
    title: str,
    value_label: str,
    source: str,
    category_label: str = "State",
    lower: Sequence[float] | None = None,
    upper: Sequence[float] | None = None,
    unit: str = "percent",
    decimals: int = 1,
    interval_label: str = DEFAULT_INTERVAL_LABEL,
    extra_columns: Sequence[tuple[str, Sequence[str]]] = (),
    rings: Mapping[str, Sequence[float]] | None = None,
    attribution: str = "",
    themes: Mapping[str, MapTheme] | None = None,
    chart_id: str = "map",
    lang: str = "en",
    patterns: bool | None = None,
    scheme: str = DEFAULT_SCHEME,
    legend_filter: bool = True,
) -> dict[str, Any]:
    """A choropleth document (see the module docstring).

    ``names``, ``codes`` and ``values`` (and ``lower``/``upper``) have one entry per region;
    ``paths`` maps each code to its SVG path in ``view_box`` units. ``breaks`` are the
    increasing class boundaries (one class more than breaks); every theme needs exactly that
    many fills. ``extra_columns`` adds text columns to the table, e.g. a precision flag.
    ``rings`` (code -> [cx, cy, r]) marks small regions so they can be found.
    ``patterns`` gives each class a pattern tile: ``None`` (the default) turns them on for
    five classes or fewer and off for more; ``True`` needs five classes or fewer.

    New in 0.3: ``scheme`` picks the colours (a key of :data:`MAP_SCHEMES`; **the default
    changed** from the greens to ``"ylgnbu"``) and the pattern style: ``"green"`` is the
    whole 0.2 look (0.2 pattern order, one ink per theme); any other scheme orders the
    patterns by ink weight with an ink per class. ``themes``, when given, replaces the
    scheme's colours only. ``legend_filter`` adds what a page needs for a legend whose
    items show one class at a time (each class's regions and announcement).
    """
    _lang.get(lang)
    if scheme not in MAP_SCHEMES:
        known = ", ".join(MAP_SCHEMES)
        raise ValueError(f"unknown map scheme {scheme!r}; available: {known}")
    themes_given = themes
    themes = dict(themes or MAP_SCHEMES[scheme])
    legacy = scheme == "green"
    if "light" not in themes:
        raise ValueError("a 'light' theme is required; it is the default rendering")
    if not (len(names) == len(codes) == len(values)):
        raise ValueError("names, codes and values must have one entry per region")
    if len(names) < 2:
        raise ValueError("a map needs at least two regions")
    if len(set(codes)) != len(codes):
        raise ValueError("region codes must be unique")
    missing = [c for c in codes if c not in paths]
    if missing:
        raise ValueError(f"no map path for {', '.join(missing)}")
    if not breaks or list(breaks) != sorted(set(breaks)):
        raise ValueError("breaks must be strictly increasing, with at least one")
    for name, theme in themes.items():
        if len(theme.classes) != len(breaks) + 1:
            raise ValueError(
                f"theme {name!r} has {len(theme.classes)} fills for {len(breaks) + 1} classes"
            )
    if patterns is None:
        patterns = len(breaks) + 1 <= len(PATTERNS)
    if not patterns:
        tiles: tuple[Any, ...] = ()
    elif legacy or len(breaks) + 1 > len(PATTERNS):
        tiles = assign(len(breaks) + 1)  # raises with more than five classes
    else:
        tiles = assign_map(len(breaks) + 1)
    for label, column in extra_columns:
        if len(column) != len(names):
            raise ValueError(f"extra column {label!r} needs one entry per region")
    data = ChartData(
        categories=tuple(names),
        series=(
            Series(
                value_label,
                tuple(values),
                None if lower is None else tuple(lower),
                None if upper is None else tuple(upper),
            ),
        ),
        unit=unit,
        decimals=decimals,
        verbatim=(title, source),
        interval_label=interval_label,
        category_label=category_label,
    )
    labels = class_labels(breaks, unit)
    class_index = [classify(v, breaks, decimals) for v in values]
    classes = [
        {
            "label": label,
            "lower": None if k == 0 else breaks[k - 1],
            "upper": None if k == len(breaks) else breaks[k],
            "count": class_index.count(k),
        }
        for k, label in enumerate(labels)
    ]
    alt_text, class_sentence, _ = _alt_text(data, classes, title=title, source=source, lang=lang)
    pattern_block: dict[str, Any] | None = None
    if patterns:
        for c, tile in zip(classes, tiles, strict=True):
            c["pattern"] = tile.id
        pattern_block = {
            "tiles": {tile.id: tile_dict(tile) for tile in tiles},
            "classes": [tile.id for tile in tiles],
            "sequence": "density-0.2" if legacy else "ink-weight",
        }
        if legacy:
            # One ink per theme, as in 0.2 (no class_ink; a page falls back to this).
            pattern_block["ink"] = {name: ink_for(t.classes) for name, t in themes.items()}
        else:
            pattern_block["class_ink"] = {
                name: class_inks(tiles, t.classes) for name, t in themes.items()
            }
        pattern_block["scale"] = tile_scale(view_box, max(tile.size for tile in tiles))
    legend: dict[str, Any] | None = None
    if legend_filter:
        members = [
            sorted(n for n, k in zip(names, class_index, strict=True) if k == j)
            for j in range(len(classes))
        ]
        label = _lang.get(lang).label(category_label)
        sentences, everything = _announcements(classes, members, label=label, lang=lang)
        for c, regions_in, sentence in zip(classes, members, sentences, strict=True):
            c["regions"] = regions_in
            c["announce"] = sentence
        t = _lang.get(lang).MAP_LEGEND
        legend = {
            "filter": True,
            "announce_all": everything,
            "templates": {k: t[k] for k in ("filter_class", "filter_empty", "filter_all")},
        }
    doc: dict[str, Any] = {
        "id": chart_id,
        "title": title,
        "map": {
            "viewBox": view_box,
            "paths": {code: paths[code] for code in codes},
            "rings": {c: list(r) for c, r in (rings or {}).items() if c in set(codes)},
            "attribution": attribution,
        },
        "regions": [
            {"code": code, "name": name, "class": k}
            for code, name, k in zip(codes, names, class_index, strict=True)
        ],
        "breaks": list(breaks),
        "classes": classes,
        "themes": {name: t.to_dict() for name, t in themes.items()},
        "alt_text": alt_text,
        "alt_text_classes": class_sentence,
        "table": _table(
            data,
            names,
            class_index,
            labels,
            extra_columns,
            title=title,
            source=source,
            value_label=value_label,
        ),
        "data": data.to_dict(),
        "keyboard": {
            # The map is one image: its states are not separate Tab stops. Every value is in
            # the table; the page adds a tooltip on hover, tap and focus as an extra.
            "interactive": False,
            "hover_only_data": False,
            "data_route": "table",
            "tooltip": "hover, tap and focus; Esc closes it (WCAG 2.2 SC 1.4.13)",
            # New in 0.3: the legend's items are toggle buttons that show one class.
            "legend_filter": legend_filter,
            **(
                {
                    "legend_keys": "Tab to a legend button; Enter or Space shows only that "
                    "class (aria-pressed) or, pressed again, all; Esc shows all"
                }
                if legend_filter
                else {}
            ),
        },
        "meta": {
            "experimental": False,
            "generator": "disability_access_charts.maps.choropleth",
            "library_version": __version__,
            "schema": SCHEMA,
            "chart_type": "choropleth",
            "source": source,
            "alt_text_source": "data",
            "alt_text_lang": lang,
            "classed_on": f"values rounded to {decimals} decimal(s), as displayed",
            "scheme": scheme if themes_given is None else "custom",
        },
    }
    if pattern_block is not None:
        doc["patterns"] = pattern_block
    if legend is not None:
        doc["legend"] = legend
    from disability_access_charts.audit import audit

    doc["audit"] = audit(doc)
    return doc


def tile_scale(view_box: str, size: int) -> float:
    """How much to scale a tile so it is 1/52 of the map's width: about 12 pixels when the
    map is drawn 630 pixels wide, as on Curb Cut's page."""
    try:
        width = float(view_box.split()[2])
    except (IndexError, ValueError):
        raise ValueError(f"view_box must be 'x y width height', got {view_box!r}") from None
    return round(width / 52 / size, 4)


# --- Audit --------------------------------------------------------------------------------


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


def _contrast(
    criterion: str, theme: str, what: str, fg: str, bg: str, minimum: float, against: str
) -> dict[str, Any]:
    ratio = contrast_ratio(fg, bg)
    return {
        "id": f"wcag-{criterion}",
        "wcag": criterion,
        "severity": "error",
        "theme": theme,
        "description": f"{what} against {against}",
        "foreground": fg,
        "background": bg,
        "ratio": round(ratio, 2),
        "minimum": minimum,
        "passed": ratio >= minimum,
    }


def _casing(theme: str, edge: str, halo: str, colour: str, against: str) -> dict[str, Any]:
    """One cased-boundary check: the edge or the halo is 3:1 against ``colour``."""
    edge_ratio = contrast_ratio(edge, colour)
    halo_ratio = contrast_ratio(halo, colour)
    best = max(edge_ratio, halo_ratio)
    return {
        "id": "wcag-1.4.11",
        "wcag": "1.4.11",
        "severity": "error",
        "theme": theme,
        "description": f"State boundaries (edge or halo) against {against}",
        "foreground": edge if edge_ratio >= halo_ratio else halo,
        "background": colour,
        "ratio": round(best, 2),
        "edge_ratio": round(edge_ratio, 2),
        "halo_ratio": round(halo_ratio, 2),
        "minimum": NON_TEXT_MIN,
        "passed": best >= NON_TEXT_MIN,
    }


def _vision_checks(theme: str, fills: Sequence[str]) -> list[dict[str, Any]]:
    """Neighbouring fills under normal and simulated colour vision (CIEDE2000)."""
    differences = neighbour_differences(fills)
    lowest = {vision: min(d) if d else None for vision, d in differences.items()}
    values = [v for v in lowest.values() if v is not None]
    low = min(values) if values else None
    worst = [v for v in SIMULATIONS if lowest[v] == low]
    extra = {
        "theme": theme,
        "simulation": "Machado et al. 2009, severity 1.0; CIEDE2000",
        "min_delta_e": low,
        "worst_vision": worst[0] if worst else None,
        "min_delta_e_by_vision": lowest,
        "neighbour_delta_e": differences,
    }
    return [
        _check(
            "colour-vision",
            "1.4.1",
            "error",
            "Neighbouring class fills stay distinguishable under normal vision and simulated "
            f"deuteranopia, protanopia and tritanopia (CIEDE2000 at least {CVD_MIN_DELTA_E:g})",
            low is None or low >= CVD_MIN_DELTA_E,
            minimum=CVD_MIN_DELTA_E,
            **extra,
        ),
        _check(
            "colour-vision-target",
            "1.4.1",
            "warning",
            "Neighbouring class fills reach the target difference under normal and simulated "
            f"colour vision (CIEDE2000 at least {CVD_TARGET_DELTA_E:g})",
            low is None or low >= CVD_TARGET_DELTA_E,
            minimum=CVD_TARGET_DELTA_E,
            theme=theme,
            min_delta_e=low,
        ),
    ]


def _theme_checks(themes: Mapping[str, MapTheme]) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    for name, t in themes.items():
        checks.append(
            _contrast("1.4.3", name, "Text colour", t.text, t.background, TEXT_MIN, "background")
        )
        checks.append(
            _contrast(
                "1.4.11",
                name,
                "State boundaries and legend swatch outlines",
                t.edge,
                t.background,
                NON_TEXT_MIN,
                "background",
            )
        )
        if t.halo is None:
            # One boundary colour (0.2): 3:1 against every fill.
            for k, fill in enumerate(t.classes):
                checks.append(
                    _contrast(
                        "1.4.11",
                        name,
                        "State boundaries",
                        t.edge,
                        fill,
                        NON_TEXT_MIN,
                        f"class {k + 1} fill",
                    )
                )
        else:
            # Cased boundaries (0.3): the edge stands out from its halo, and one of the two
            # stands out from the background and from every fill.
            checks.append(
                _contrast(
                    "1.4.11",
                    name,
                    "Boundary edge",
                    t.edge,
                    t.halo,
                    NON_TEXT_MIN,
                    "its halo",
                )
            )
            targets = [("background", t.background)] + [
                (f"class {k + 1} fill", fill) for k, fill in enumerate(t.classes)
            ]
            for against, colour in targets:
                checks.append(_casing(name, t.edge, t.halo, colour, against))
        checks += _vision_checks(name, t.classes)
        lum = [relative_luminance(c) for c in t.classes]
        light_bg = relative_luminance(t.background) > 0.5
        ordered = all((a > b) if light_bg else (a < b) for a, b in itertools.pairwise(lum))
        checks.append(
            _check(
                "classes-ordered",
                "1.4.11",
                "error",
                "Class fills move away from the background as the value rises",
                ordered,
                theme=name,
            )
        )
    return checks


def keyboard_block(doc: Mapping[str, Any]) -> Mapping[str, Any]:
    return doc.get("keyboard") or {}


def _legend_check(
    doc: Mapping[str, Any], data: ChartData, expected: Sequence[int], labels: Sequence[str]
) -> dict[str, Any]:
    """The legend filter's regions and announcements, regenerated from the data."""
    classes = doc.get("classes", [])
    problems: list[str] = []
    members = [
        sorted(n for n, k in zip(data.categories, expected, strict=True) if k == j)
        for j in range(len(labels))
    ]
    lang = doc.get("meta", {}).get("alt_text_lang", "en")
    label = _lang.get(lang).label(data.category_label)
    want_classes = [{"label": lab} for lab in labels]
    sentences, everything = _announcements(want_classes, members, label=label, lang=lang)
    if len(classes) != len(labels):
        problems.append("the classes differ from the breaks")
    else:
        for k, c in enumerate(classes):
            if c.get("regions") != members[k]:
                problems.append(f"class {k + 1}: its regions differ from the data")
            if c.get("announce") != sentences[k]:
                problems.append(f"class {k + 1}: its announcement differs from the data")
    legend = doc.get("legend") or {}
    if legend.get("filter") is not True:
        problems.append("the document has no legend filter block")
    if legend.get("announce_all") != everything:
        problems.append("the 'show all' announcement differs from the data")
    return _check(
        "legend-filter-matches-data",
        "1.1.1",
        "error",
        "Each legend item lists the regions in its class, and the sentence the page announces "
        "when it shows one class (or all) matches the data",
        not problems,
        problems=problems,
    )


def map_checks(doc: Mapping[str, Any], alt_text: str | None = None) -> list[dict[str, Any]]:
    """Every audit check for a choropleth document."""
    from disability_access_charts.audit import alt_text_checks

    themes = {
        name: MapTheme(**{**t, "classes": tuple(t["classes"])}) for name, t in doc["themes"].items()
    }
    checks = _theme_checks(themes)
    data = ChartData.from_dict(doc["data"])
    series = data.series[0]
    breaks = list(doc.get("breaks", []))
    decimals = data.decimals
    regions = doc.get("regions", [])
    classes = doc.get("classes", [])
    labels = class_labels(breaks, data.unit) if breaks else []

    # The classes, regions, map and table against the data.
    problems: list[str] = []
    expected = [classify(v, breaks, decimals) for v in series.values]
    if [r.get("name") for r in regions] != list(data.categories):
        problems.append("the regions differ from the data's categories")
    elif [r.get("class") for r in regions] != expected:
        problems.append("a region's class differs from its value")
    if [c.get("label") for c in classes] != labels:
        problems.append("the class labels differ from the breaks")
    elif [c.get("count") for c in classes] != [expected.count(k) for k in range(len(labels))]:
        problems.append("a class count differs from the data")
    paths = (doc.get("map") or {}).get("paths", {})
    codes = [r.get("code") for r in regions]
    if set(paths) != set(codes):
        problems.append("the map's paths differ from the regions")
    table = doc.get("table") or {}
    keys = [c.get("key") for c in table.get("columns", [])]
    rows = table.get("rows", [])
    by_name = {str(r[0]): r for r in rows}
    if sorted(by_name) != sorted(data.categories) or len(rows) != len(data.categories):
        problems.append("the table does not hold every region once")
    else:
        for i, name in enumerate(data.categories):
            row = by_name[name]
            want = {"value": series.values[i], "class": labels[expected[i]] if labels else None}
            if series.lower is not None and series.upper is not None:
                want |= {"lower": series.lower[i], "upper": series.upper[i]}
            for key, value in want.items():
                if key not in keys:
                    problems.append(f"the table has no {key!r} column")
                    continue
                got = row[keys.index(key)]
                same = got == value if isinstance(value, str) else abs(float(got) - value) < 1e-9
                if not same:
                    problems.append(f"{name}: the table's {key} differs from the data")
    checks.append(
        _check(
            "map-matches-data",
            "1.1.1",
            "error",
            "The classes, the map's regions and the table show the numbers in the data block",
            not problems,
            problems=problems,
        )
    )
    empty = [c["label"] for c in classes if c.get("count") == 0]
    checks.append(
        _check(
            "class-empty",
            "1.1.1",
            "warning",
            "Every class has at least one region (an empty class wastes a colour step)",
            not empty,
            problems=empty,
        )
    )

    block = doc.get("patterns")
    if block is not None:
        checks += pattern_checks(
            list(block.get("classes", [])),
            block.get("tiles", {}),
            {name: list(t.classes) for name, t in themes.items()},
            block.get("ink", {}),
            what="class",
            legend_patterns=[c.get("pattern") for c in classes],
            class_ink=block.get("class_ink"),
        )

    if keyboard_block(doc).get("legend_filter"):
        checks.append(_legend_check(doc, data, expected, labels))

    # Colour is not the only cue: legend ranges, the table's class column, the tooltip.
    adjacent = {
        name: [
            round(contrast_ratio(a, b), 2) for a, b in zip(t.classes, t.classes[1:], strict=False)
        ]
        for name, t in themes.items()
    }
    keyboard = doc.get("keyboard") or {}
    cue_problems = []
    if not classes or not all(c.get("label") for c in classes):
        cue_problems.append("the legend has no range label for every class")
    if "class" not in keys:
        cue_problems.append("the table has no class column")
    if keyboard.get("data_route") != "table":
        cue_problems.append("the keyboard route to the data is not the table")
    checks.append(
        _check(
            "not-colour-alone",
            "1.4.1",
            "error",
            "Colour is not the only way to read a state's class: the legend gives each range "
            "in words, the table gives every value and class, and boundaries are 3:1",
            not cue_problems,
            problems=cue_problems,
            adjacent_class_ratios=adjacent,
            note=(
                "Neighbouring class fills are under 3:1 apart (a five-step sequential scale "
                "cannot reach 3:1 between neighbours), so the map's classes are also given "
                "in words (legend, table, tooltip); boundaries meet 3:1 against the background "
                "and every fill (with a cased boundary, its edge or its halo does)."
                + (
                    " Each class also has its own pattern, at 3:1 against its fill (see the "
                    "patterns checks)."
                    if block is not None
                    else ""
                )
            ),
        )
    )
    if block is None:
        checks.append(
            _check(
                "shade-alone",
                "1.4.1",
                "warning",
                "Neighbouring classes differ by more than a shade: no patterns, so on the map "
                "itself they differ by shade alone (patterns need five classes or fewer)",
                False,
            )
        )
    checks.append(
        _check(
            "keyboard-metadata",
            "2.1.1",
            "error",
            "No information is only in the hover tooltip; the table is the route to the data",
            keyboard.get("hover_only_data") is False and keyboard.get("data_route") == "table",
        )
    )

    # Alt-text: the class sentence must be the one the data gives; the rest goes through
    # the claim checker like any chart's alt-text.
    text = alt_text if alt_text is not None else doc.get("alt_text")
    sentence = doc.get("alt_text_classes", "")
    label = _lang.get(doc.get("meta", {}).get("alt_text_lang", "en")).label(data.category_label)
    want_classes = [{"label": lab, "count": expected.count(k)} for k, lab in enumerate(labels)]
    want_sentence = _class_sentence(want_classes, label) if labels else ""
    in_text = bool(text) and bool(sentence) and sentence in (text or "")
    checks.append(
        _check(
            "alt-text-classes-match-data",
            "1.1.1",
            "error",
            "The alt-text gives each class's range and its number of regions, from the data",
            in_text and sentence == want_sentence,
        )
    )
    rest = (text or "").replace(sentence, "", 1).replace("  ", " ") if in_text else text
    checks += alt_text_checks(rest, data, lang=doc.get("meta", {}).get("alt_text_lang", "en"))
    return checks
