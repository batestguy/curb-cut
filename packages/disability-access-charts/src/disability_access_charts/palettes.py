"""Colour themes and the series palette.

Every colour here is checked by the tests: marks and series colours at least 3:1 against the
background (WCAG 2.2 SC 1.4.11), text at least 4.5:1 (SC 1.4.3). Series are also told apart
by marker shape (:data:`SYMBOLS`), so colour is never the only cue (SC 1.4.1).
"""

from __future__ import annotations

from dataclasses import dataclass

# Okabe & Ito (2008), "Color Universal Design", https://jfly.uni-koeln.de/color/ . Eight
# colours chosen to stay distinguishable with the common colour-vision deficiencies.
OKABE_ITO: dict[str, str] = {
    "black": "#000000",
    "orange": "#e69f00",
    "sky_blue": "#56b4e9",
    "bluish_green": "#009e73",
    "yellow": "#f0e442",
    "blue": "#0072b2",
    "vermillion": "#d55e00",
    "reddish_purple": "#cc79a7",
}

# Plotly marker symbols, one per series, so the legend and the dots don't rely on colour.
SYMBOLS: tuple[str, ...] = (
    "circle",
    "diamond",
    "square",
    "triangle-up",
    "x",
    "star",
)


@dataclass(frozen=True)
class Theme:
    """Colours for one colour scheme.

    ``mark`` is the bar fill. ``highlight`` (optional) is the fill for one selected bar; it
    must differ from both the background and ``mark`` by at least 3:1, and a page that uses
    it should add a non-colour cue too (an outline, a bold label). ``series`` are the colours
    for multi-series charts (dot plots), in order; each must be 3:1 against the background.
    """

    background: str
    text: str
    mark: str
    grid: str
    highlight: str | None = None
    series: tuple[str, ...] = ()


# Nigerian flag green. Light: the flag green #008751 on white (about 4.6:1), with a deep
# indigo highlight (about 3.5:1 against the green). Dark: with light green bars, the only
# colours 3:1 from both them and the background are dim mid-tones (a crimson such as
# #c31e55, about 3.2:1), which read as "darker", not "selected". So the bars are a mid green
# (about 4.1:1 on near-black) and the highlight is a light gold (about 3.5:1 against them).
#
# Series: the Okabe-Ito colours that reach 3:1 on each background (verification.md D35).
# On white: blue 5.19, vermillion 3.87, bluish green 3.42, reddish purple 3.06 (orange 2.25,
# sky blue 2.31 and yellow 1.32 fail). On #121212: orange 8.32, sky blue 8.12, bluish green
# 5.48, yellow 14.17, reddish purple 6.12, vermillion 4.84.
DEFAULT_THEMES: dict[str, Theme] = {
    "light": Theme(
        background="#ffffff",
        text="#1a1a1a",
        mark="#008751",
        grid="#d9d9d9",
        highlight="#1b1464",
        series=(
            OKABE_ITO["blue"],
            OKABE_ITO["vermillion"],
            OKABE_ITO["bluish_green"],
            OKABE_ITO["reddish_purple"],
        ),
    ),
    "dark": Theme(
        background="#121212",
        text="#f0f0f0",
        mark="#198754",
        grid="#3a3a3a",
        highlight="#ffe08a",
        series=(
            OKABE_ITO["orange"],
            OKABE_ITO["sky_blue"],
            OKABE_ITO["bluish_green"],
            OKABE_ITO["yellow"],
            OKABE_ITO["reddish_purple"],
            OKABE_ITO["vermillion"],
        ),
    ),
}
