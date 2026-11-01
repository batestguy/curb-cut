"""Pattern fills: five abstract tiles inspired by adire, drawn for this library.

Patterns give a second, non-colour cue for series in a bar chart and for classes on a map
(WCAG 2.2 SC 1.4.1). Colour stays, and so do direct labels or a legend: a pattern is added
to the colour, never used instead of it.

The tiles
---------
Each tile is an SVG path of the regions to fill in a ``size`` x ``size`` square, the form
Plotly's ``marker.pattern.path`` takes (bar, pie and histogram traces; not scatter or
choropleth, ``docs/verification.md`` D30). The same path draws the map's SVG ``<pattern>``
fills. In :data:`PATTERNS` order, from the sparsest to the densest ink, so a sequential
map reads as ordered without colour too:

* ``dots``: two small dots per tile, after the tied dots of oniko;
* ``rings``: one ring per tile, after oniko's tie-resist circles;
* ``checks``: a square grid, after the checked layouts of adire;
* ``lines``: diagonal lines, after the line work in adire;
* ``crosshatch``: diagonal lines both ways.

They are plain geometry, drawn here, and none copies a cloth. They are **not** nsibidi or
Ukara signs, which carry meanings that are not ours to use (``docs/verification.md`` D31;
sources in ``docs/patterns.md``).

Map sequence (new in 0.3)
-------------------------
Maps use their own order, :data:`MAP_PATTERNS`, **by ink weight** so the lowest class is the
lightest: ``plain`` (no ink, about 0% of the tile), ``dots`` (about 7%), ``lines`` (about
22%), ``crosshatch`` (about 33%) and ``solid`` (no ink: the class's own fill, the darkest in
the light theme, carries it). ``plain`` and ``solid`` draw nothing, so they are told apart
by their fills alone; :func:`assign_map` never makes them neighbours, and the audit checks
that their fills are 3:1 apart. Fewer classes take an ordered subset (:data:`MAP_SEQUENCES`):
two classes get plain and crosshatch, three plain, lines and solid, four plain, dots,
crosshatch and solid. Bars keep :data:`PATTERNS`, unchanged.

The ink rule
------------
Bars, and maps drawn with ``scheme="green"`` (the 0.2 look), use one ink colour per theme,
black or white, whichever has the higher *lowest* contrast against the fills it sits on
(:func:`ink_for`). Maps in the other schemes (0.3) give **each class its own ink**, black or
white, whichever contrasts more with that class's fill (:func:`class_inks`); a class whose
tile draws nothing has no ink. Where the pattern is what tells two neighbouring classes or
series apart, the ink must reach 3:1 against the fill it sits on (SC 1.4.11, non-text
contrast); the audit checks this for every inked class or series in every theme.
"""

from __future__ import annotations

import html
import itertools
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from disability_access_charts.contrast import NON_TEXT_MIN, contrast_ratio

TILE = 12
"""The side of every tile, in Plotly pattern pixels (or SVG user units before scaling)."""

BLACK = "#000000"
WHITE = "#ffffff"


@dataclass(frozen=True)
class Pattern:
    """One tile: ``path`` is the region to fill in a ``size`` x ``size`` square."""

    id: str
    name: str
    path: str
    inspiration: str
    size: int = TILE


def _circle(cx: float, cy: float, r: float, *, clockwise: bool = True) -> str:
    """A circle as two arcs. Rings pair a clockwise outer circle with an anticlockwise inner
    one, so the hole stays empty under both the nonzero and the even-odd fill rule."""
    sweep = 1 if clockwise else 0
    return (
        f"M{cx - r:g},{cy:g}a{r:g},{r:g} 0 1,{sweep} {2 * r:g},0"
        f"a{r:g},{r:g} 0 1,{sweep} {-2 * r:g},0Z"
    )


def _diagonal(w: float, *, rising: bool) -> str:
    """A diagonal band of half-width ``w`` (in x + y units) that joins up across tiles."""
    s = TILE
    if rising:  # from bottom left to top right: x + y = s, with corners for x + y = 0 and 2s
        parts = [
            f"M0,{s - w:g}L{s - w:g},0L{s},0L{s},{w:g}L{w:g},{s}L0,{s}Z",
            f"M0,0L{w:g},0L0,{w:g}Z",
            f"M{s},{s - w:g}L{s},{s}L{s - w:g},{s}Z",
        ]
    else:  # from top left to bottom right: y - x = 0, with corners for y - x = s and -s
        parts = [
            f"M0,0L{w:g},0L{s},{s - w:g}L{s},{s}L{s - w:g},{s}L0,{w:g}Z",
            f"M{s - w:g},0L{s},0L{s},{w:g}Z",
            f"M0,{s - w:g}L{w:g},{s}L0,{s}Z",
        ]
    return "".join(parts)


DOTS = Pattern(
    "dots",
    "Dots",
    _circle(3, 3, 1.3) + _circle(9, 9, 1.3),
    "Oniko: small tied dots (tie-resist adire)",
)
RINGS = Pattern(
    "rings",
    "Rings",
    _circle(6, 6, 3.6) + _circle(6, 6, 2.3, clockwise=False),
    "Oniko: tie-resist circles (adire oniko)",
)
CHECKS = Pattern(
    "checks",
    "Checks",
    f"M0,0H{TILE}V1.2H0Z" + f"M0,1.2H1.2V{TILE}H0Z",
    "The checked grids of adire layouts",
)
LINES = Pattern(
    "lines",
    "Lines",
    _diagonal(1.3, rising=True),
    "Line work in adire (stitched and drawn stripes)",
)
CROSSHATCH = Pattern(
    "crosshatch",
    "Crosshatch",
    _diagonal(1.1, rising=True) + _diagonal(1.1, rising=False),
    "Crossed lines, as in adire's line work drawn both ways",
)

PATTERNS: tuple[Pattern, ...] = (DOTS, RINGS, CHECKS, LINES, CROSSHATCH)
"""The five tiles, from the sparsest ink to the densest (bars, and 0.2 maps)."""

PLAIN = Pattern("plain", "Plain", "", "No pattern: the fill alone (the lowest map class)")
SOLID = Pattern("solid", "Solid", "", "No pattern: the fill alone (the highest map class)")

MAP_PATTERNS: tuple[Pattern, ...] = (PLAIN, DOTS, LINES, CROSSHATCH, SOLID)
"""The map sequence (new in 0.3), by ink weight: plain, dots, lines, crosshatch, solid."""

MAP_SEQUENCES: dict[int, tuple[Pattern, ...]] = {
    2: (PLAIN, CROSSHATCH),
    3: (PLAIN, LINES, SOLID),
    4: (PLAIN, DOTS, CROSSHATCH, SOLID),
    5: MAP_PATTERNS,
}
"""The tiles a map with 2 to 5 classes gets, lowest class first; two no-ink tiles are never
neighbours."""

_BY_ID = {p.id: p for p in (*PATTERNS, PLAIN, SOLID)}


def get(pattern_id: str) -> Pattern:
    """The tile with this id; unknown ids raise ``ValueError``."""
    try:
        return _BY_ID[pattern_id]
    except KeyError:
        known = ", ".join(_BY_ID)
        raise ValueError(f"unknown pattern {pattern_id!r}; available: {known}") from None


def assign(n: int) -> tuple[Pattern, ...]:
    """The first ``n`` tiles, one per series or class; at most five."""
    if n > len(PATTERNS):
        raise ValueError(f"at most {len(PATTERNS)} patterns (one per series or class), got {n}")
    return PATTERNS[:n]


def assign_map(n: int) -> tuple[Pattern, ...]:
    """The map tiles for ``n`` classes (:data:`MAP_SEQUENCES`); 2 to 5 classes."""
    try:
        return MAP_SEQUENCES[n]
    except KeyError:
        raise ValueError(f"map patterns need 2 to 5 classes, got {n}") from None


def has_ink(tile: Pattern | Mapping[str, Any]) -> bool:
    """Whether a tile (a :class:`Pattern` or a document's tile dict) draws any ink."""
    path = tile.path if isinstance(tile, Pattern) else tile.get("path")
    return bool(path)


def best_ink(fill: str) -> str:
    """Black or white: whichever contrasts more with ``fill`` (black on a tie)."""
    return BLACK if contrast_ratio(BLACK, fill) >= contrast_ratio(WHITE, fill) else WHITE


def class_inks(tiles: Sequence[Pattern], fills: Sequence[str]) -> list[str | None]:
    """Each class's ink (:func:`best_ink` of its fill), or ``None`` where its tile has no ink."""
    return [best_ink(f) if has_ink(t) else None for t, f in zip(tiles, fills, strict=True)]


def ink_for(fills: Sequence[str]) -> str:
    """Black or white: whichever has the higher lowest contrast against ``fills``."""
    if not fills:
        return BLACK
    black = min(contrast_ratio(BLACK, f) for f in fills)
    white = min(contrast_ratio(WHITE, f) for f in fills)
    return BLACK if black >= white else WHITE


def plotly_pattern(pattern: Pattern, *, ink: str, fill: str) -> dict[str, Any]:
    """Plotly ``marker.pattern`` for a bar trace: ``ink`` on the bar's own ``fill``."""
    return {
        "path": pattern.path,
        "size": pattern.size,
        "fgcolor": ink,
        "bgcolor": fill,
        "fgopacity": 1,
        "fillmode": "overlay",
    }


def svg_pattern(
    pattern: Pattern, *, pattern_id: str, ink: str | None, fill: str, scale: float = 1.0
) -> str:
    """An SVG ``<pattern>`` element: the tile's ``ink`` on a ``fill`` background.

    ``scale`` sizes the tile in the user units of the shape that uses it (on a map, the
    ``viewBox`` units). Put it in a ``<defs>`` and fill a shape with ``url(#pattern_id)``.
    A tile with no ink (``plain``, ``solid``) is the fill alone, and takes ``ink=None``.
    """
    s = pattern.size
    pid = html.escape(pattern_id, quote=True)
    path = ""
    if pattern.path:
        if ink is None:
            raise ValueError(f"pattern {pattern.id!r} draws ink, so it needs an ink colour")
        path = f'<path d="{pattern.path}" fill="{html.escape(ink, quote=True)}"/>'
    return (
        f'<pattern id="{pid}" patternUnits="userSpaceOnUse" width="{s}" height="{s}" '
        f'patternTransform="scale({scale:g})">'
        f'<rect width="{s}" height="{s}" fill="{html.escape(fill, quote=True)}"/>'
        f"{path}</pattern>"
    )


def tile_dict(pattern: Pattern) -> dict[str, Any]:
    """A tile as a document stores it."""
    return {
        "id": pattern.id,
        "name": pattern.name,
        "path": pattern.path,
        "size": pattern.size,
        "inspiration": pattern.inspiration,
    }


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


def pattern_checks(
    assigned: Sequence[str | None],
    tiles: Mapping[str, Mapping[str, Any]],
    fills: Mapping[str, Sequence[str]],
    ink: Mapping[str, str],
    *,
    what: str,
    legend_patterns: Sequence[str | None],
    drawn: Sequence[str | None] | None = None,
    class_ink: Mapping[str, Sequence[str | None]] | None = None,
) -> list[dict[str, Any]]:
    """The audit's pattern checks, shared by bar charts and maps.

    ``assigned`` is each series' (or class's) pattern id, in order; ``tiles`` the document's
    tiles by id; ``fills`` each theme's colours in the same order; ``ink`` each theme's
    pattern ink; ``legend_patterns`` the pattern the legend shows for each; ``drawn`` (bars)
    the path each Plotly trace actually draws. ``class_ink`` (maps, new in 0.3) gives each
    theme's ink per class (``None`` for a tile that draws no ink); with it, ``ink`` is not
    used.
    """
    checks: list[dict[str, Any]] = []
    problems: list[str] = []
    plural = _plural(what)
    n = len(assigned)
    if any(p is None for p in assigned):
        problems.append(f"a {what} has no pattern")
    ids = [p for p in assigned if p is not None]
    if len(set(ids)) != len(ids):
        problems.append(f"two {plural} share a pattern")
    paths = [tiles.get(p, {}).get("path") for p in ids]
    if any(p is None for p in paths):
        problems.append("a pattern id has no tile in the document")
    else:
        inked = [p for p in paths if p]
        if len(set(inked)) != len(inked):
            problems.append(f"two {what} patterns draw the same tile")
    # Tiles with no ink (plain, solid) are told apart by their fills alone: never neighbours,
    # and their fills at least 3:1 apart in every theme.
    blank = [
        i for i, p in enumerate(assigned) if p is not None and tiles.get(p, {}).get("path") == ""
    ]
    if any(b - a == 1 for a, b in itertools.pairwise(blank)):
        problems.append(f"two neighbouring {plural} both have a pattern with no ink")
    for name, colours in fills.items():
        if len(colours) != n:
            problems.append(f"theme {name!r} has {len(colours)} colours for {n} patterns")
            continue
        if len({c.lower() for c in colours}) != len(colours):
            problems.append(f"theme {name!r}: two {what} colours are the same")
        for a, b in itertools.combinations(blank, 2):
            ratio = contrast_ratio(colours[a], colours[b])
            if ratio < NON_TEXT_MIN:
                problems.append(
                    f"theme {name!r}: {what} {a + 1} and {b + 1} have no ink and their fills "
                    f"are only {ratio:.2f}:1 apart"
                )
    if drawn is not None:
        want = [tiles.get(p or "", {}).get("path") for p in assigned]
        if list(drawn) != want:
            problems.append("a trace draws a different pattern from the one assigned to it")
    checks.append(
        _check(
            "patterns-one-to-one",
            "1.4.1",
            "error",
            f"Each {what} has its own pattern and its own colour, one to one",
            not problems,
            problems=problems,
        )
    )
    if class_ink is not None:
        checks += _class_ink_checks(assigned, tiles, fills, class_ink, what=what)
    else:
        checks += _theme_ink_checks(fills, ink, what=what)
    missing = [
        i + 1
        for i, (want, got) in enumerate(zip(assigned, legend_patterns, strict=False))
        if want is None or got != want
    ]
    if len(legend_patterns) != n:
        missing = list(range(1, n + 1))
    checks.append(
        _check(
            "patterns-legend",
            "1.4.1",
            "error",
            f"The legend shows each {what}'s pattern next to its colour",
            not missing,
            problems=[f"{what} {i}" for i in missing],
        )
    )
    return checks


def _plural(what: str) -> str:
    return {"class": "classes", "series": "series"}.get(what, what + "s")


def _theme_ink_checks(
    fills: Mapping[str, Sequence[str]], ink: Mapping[str, str], *, what: str
) -> list[dict[str, Any]]:
    """One ink per theme (bars, 0.2 maps): 3:1 against every fill it sits on."""
    checks: list[dict[str, Any]] = []
    for name, colours in fills.items():
        theme_ink = ink.get(name)
        if theme_ink is None:
            checks.append(
                _check(
                    "patterns-ink-contrast",
                    "1.4.11",
                    "error",
                    f"Theme {name!r} has no pattern ink",
                    False,
                    theme=name,
                )
            )
            continue
        ratios = [round(contrast_ratio(theme_ink, c), 2) for c in colours]
        low = [f"{c} ({r}:1)" for c, r in zip(colours, ratios, strict=True) if r < NON_TEXT_MIN]
        checks.append(
            _check(
                "patterns-ink-contrast",
                "1.4.11",
                "error",
                f"Pattern ink is at least 3:1 against every {what} fill it sits on",
                not low,
                theme=name,
                ink=theme_ink,
                ratios=ratios,
                minimum=NON_TEXT_MIN,
                problems=low,
            )
        )
    return checks


def _class_ink_checks(
    assigned: Sequence[str | None],
    tiles: Mapping[str, Mapping[str, Any]],
    fills: Mapping[str, Sequence[str]],
    class_ink: Mapping[str, Sequence[str | None]],
    *,
    what: str,
) -> list[dict[str, Any]]:
    """Ink per class (0.3 maps): 3:1 against its own fill (error) and the better of black and
    white for it (warning). A class whose tile draws no ink is exempt."""
    checks: list[dict[str, Any]] = []
    for name, colours in fills.items():
        inks = list(class_ink.get(name) or [])
        problems: list[str] = []
        ratios: list[float | None] = []
        rule: list[str] = []
        if len(inks) != len(assigned) or len(colours) != len(assigned):
            problems.append(f"theme {name!r} does not give an ink entry for every {what}")
        else:
            for k, (pid, fill, colour) in enumerate(zip(assigned, colours, inks, strict=True)):
                if not has_ink(tiles.get(pid or "", {})):
                    ratios.append(None)
                    continue
                if colour is None:
                    problems.append(f"{what} {k + 1} has a pattern but no ink")
                    ratios.append(None)
                    continue
                ratio = round(contrast_ratio(colour, fill), 2)
                ratios.append(ratio)
                if ratio < NON_TEXT_MIN:
                    problems.append(f"{what} {k + 1}: {colour} on {fill} ({ratio}:1)")
                if colour.lower() != best_ink(fill):
                    rule.append(f"{what} {k + 1}: {colour} on {fill}")
        checks.append(
            _check(
                "patterns-ink-contrast",
                "1.4.11",
                "error",
                f"Each {what}'s pattern ink is at least 3:1 against its own fill "
                f"({_plural(what)} whose pattern has no ink are exempt)",
                not problems,
                theme=name,
                ink=inks,
                ratios=ratios,
                minimum=NON_TEXT_MIN,
                problems=problems,
            )
        )
        checks.append(
            _check(
                "patterns-ink-rule",
                "1.4.11",
                "warning",
                f"Each {what}'s ink is black or white, whichever contrasts more with its fill",
                not rule,
                theme=name,
                problems=rule,
            )
        )
    return checks
