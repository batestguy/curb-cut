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
    ink_for,
    pattern_checks,
    tile_dict,
)

SCHEMA = "1.0"


@dataclass(frozen=True)
class MapTheme:
    """Colours for one colour scheme of a choropleth.

    ``classes`` are the fills, lowest class first. ``edge`` draws every boundary and outlines
    the legend swatches: it must be 3:1 against ``background`` and against every fill.
    """

    background: str
    text: str
    edge: str
    classes: tuple[str, ...]


# Five greens around the site's flag green. Light: from a pale green to the brand mark
# #008751, with near-black boundaries (3.8:1 against #008751, 15:1 against the palest).
# Dark: from a green just above the background to a mid green, with white boundaries (3.3:1
# against the brightest fill). Neighbouring fills differ by 1.3-1.6:1, which is why colour
# is never the only cue (see the module docstring).
MAP_THEMES: dict[str, MapTheme] = {
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
}


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
) -> dict[str, Any]:
    """A choropleth document (see the module docstring).

    ``names``, ``codes`` and ``values`` (and ``lower``/``upper``) have one entry per region;
    ``paths`` maps each code to its SVG path in ``view_box`` units. ``breaks`` are the
    increasing class boundaries (one class more than breaks); every theme needs exactly that
    many fills. ``extra_columns`` adds text columns to the table, e.g. a precision flag.
    ``rings`` (code -> [cx, cy, r]) marks small regions so they can be found.
    ``patterns`` gives each class a pattern tile: ``None`` (the default) turns them on for
    five classes or fewer and off for more; ``True`` needs five classes or fewer.
    """
    _lang.get(lang)
    themes = dict(themes or MAP_THEMES)
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
    tiles = assign(len(breaks) + 1) if patterns else ()
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
            "ink": {name: ink_for(t.classes) for name, t in themes.items()},
            "scale": tile_scale(view_box, max(tile.size for tile in tiles)),
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
        "themes": {name: asdict(t) for name, t in themes.items()},
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
        },
    }
    if pattern_block is not None:
        doc["patterns"] = pattern_block
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
        )

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
                "and every fill."
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
