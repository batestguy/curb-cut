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

The ink rule
------------
The pattern is drawn in one ink colour per theme, black or white, whichever has the higher
*lowest* contrast against the fills it sits on (:func:`ink_for`). Where the pattern is what
tells two neighbouring classes or series apart, the ink must reach 3:1 against every fill
it sits on (SC 1.4.11, non-text contrast); the audit checks this in every theme.
"""

from __future__ import annotations

import html
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
"""The five tiles, from the sparsest ink to the densest."""

_BY_ID = {p.id: p for p in PATTERNS}


def get(pattern_id: str) -> Pattern:
    """The tile with this id; unknown ids raise ``ValueError``."""
    try:
        return _BY_ID[pattern_id]
    except KeyError:
        known = ", ".join(p.id for p in PATTERNS)
        raise ValueError(f"unknown pattern {pattern_id!r}; available: {known}") from None


def assign(n: int) -> tuple[Pattern, ...]:
    """The first ``n`` tiles, one per series or class; at most five."""
    if n > len(PATTERNS):
        raise ValueError(f"at most {len(PATTERNS)} patterns (one per series or class), got {n}")
    return PATTERNS[:n]


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
    pattern: Pattern, *, pattern_id: str, ink: str, fill: str, scale: float = 1.0
) -> str:
    """An SVG ``<pattern>`` element: the tile's ``ink`` on a ``fill`` background.

    ``scale`` sizes the tile in the user units of the shape that uses it (on a map, the
    ``viewBox`` units). Put it in a ``<defs>`` and fill a shape with ``url(#pattern_id)``.
    """
    s = pattern.size
    pid = html.escape(pattern_id, quote=True)
    return (
        f'<pattern id="{pid}" patternUnits="userSpaceOnUse" width="{s}" height="{s}" '
        f'patternTransform="scale({scale:g})">'
        f'<rect width="{s}" height="{s}" fill="{html.escape(fill, quote=True)}"/>'
        f'<path d="{pattern.path}" fill="{html.escape(ink, quote=True)}"/>'
        "</pattern>"
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
) -> list[dict[str, Any]]:
    """The audit's pattern checks, shared by bar charts and maps.

    ``assigned`` is each series' (or class's) pattern id, in order; ``tiles`` the document's
    tiles by id; ``fills`` each theme's colours in the same order; ``ink`` each theme's
    pattern ink; ``legend_patterns`` the pattern the legend shows for each; ``drawn`` (bars)
    the path each Plotly trace actually draws.
    """
    checks: list[dict[str, Any]] = []
    problems: list[str] = []
    plural = {"class": "classes"}.get(what, what)
    n = len(assigned)
    if any(p is None for p in assigned):
        problems.append(f"a {what} has no pattern")
    ids = [p for p in assigned if p is not None]
    if len(set(ids)) != len(ids):
        problems.append(f"two {plural} share a pattern")
    paths = [tiles.get(p, {}).get("path") for p in ids]
    if any(p is None for p in paths):
        problems.append("a pattern id has no tile in the document")
    elif len(set(paths)) != len(paths):
        problems.append(f"two {what} patterns draw the same tile")
    for name, colours in fills.items():
        if len(colours) != n:
            problems.append(f"theme {name!r} has {len(colours)} colours for {n} patterns")
        elif len({c.lower() for c in colours}) != len(colours):
            problems.append(f"theme {name!r}: two {what} colours are the same")
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
