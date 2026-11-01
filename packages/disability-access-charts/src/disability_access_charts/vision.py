"""Colour-vision checks: simulated colour-vision deficiency and perceptual colour difference.

New in 0.3. Used by the map audit (:func:`disability_access_charts.maps.map_checks`) to check
that neighbouring class fills stay distinguishable for people with the three dichromacies,
not only in normal colour vision. Pure Python, no dependencies.

Simulation
----------
:func:`simulate` applies the matrices of Machado, Oliveira and Fernandes (2009), "A
physiologically-based model for simulation of color vision deficiency", IEEE Transactions on
Visualization and Computer Graphics 15(6): 1291-1298, at **severity 1.0** (full
protanopia, deuteranopia and tritanopia). The matrices act on *linear* RGB, so a colour is
decoded from sRGB, multiplied, clipped to [0, 1] and encoded again. They are the published
values (https://www.inf.ufrgs.br/~oliveira/pubs_files/CVD_Simulation/CVD_Simulation.html,
the severity-1.0 rows of the table), the same as colorspacious and DaltonLens use for
Machado's model.

Difference
----------
:func:`delta_e` is CIEDE2000 (Sharma, Wu and Dalal 2005, "The CIEDE2000 color-difference
formula: implementation notes, supplementary test data, and mathematical observations",
Color Research and Application 30(1): 21-30) between the CIELAB values of two sRGB colours
(D65 white). The tests reproduce pairs from Sharma's test data.

Thresholds
----------
These are design thresholds, not WCAG numbers: WCAG has no colour-difference criterion,
which is why a map also uses patterns and words (SC 1.4.1). A colour difference of about
2.3 is commonly quoted as just noticeable side by side (for CIELAB's ΔE*ab; Sharma 2003,
*Digital Color Imaging Handbook*); map classes must be told apart across a map and against
a legend swatch, not side by side, so both thresholds sit well above it.

* :data:`CVD_MIN_DELTA_E` = 5 (the ``colour-vision`` **error**): about twice the
  just-noticeable difference. Below it, two neighbouring classes look the same to that
  colour vision except for their patterns.
* :data:`CVD_TARGET_DELTA_E` = 10 (the ``colour-vision-target`` **warning**). ColorBrewer's
  five-class YlGnBu meets it (10.3 at its closest, protanopia, between the two lightest
  classes) and so does the library's dark YlGnBu-style palette (11.6, deuteranopia); 0.2's
  greens do not (7.5 light, 8.2 dark, both deuteranopia), so ``scheme="green"`` passes the
  error check with a warning.
"""

from __future__ import annotations

import itertools
import math
from collections.abc import Sequence

from disability_access_charts.contrast import _channels

CVD_MIN_DELTA_E = 5.0
"""The smallest CIEDE2000 difference allowed between neighbouring map fills, in every
simulation (the ``colour-vision`` error; see the module docstring)."""

CVD_TARGET_DELTA_E = 10.0
"""The CIEDE2000 difference neighbouring map fills should reach in every simulation (the
``colour-vision-target`` warning)."""

Matrix = tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]]

# Machado et al. (2009), severity 1.0, for linear RGB.
MACHADO_2009: dict[str, Matrix] = {
    "protanopia": (
        (0.152286, 1.052583, -0.204868),
        (0.114503, 0.786281, 0.099216),
        (-0.003882, -0.048116, 1.051998),
    ),
    "deuteranopia": (
        (0.367322, 0.860646, -0.227968),
        (0.280085, 0.672501, 0.047413),
        (-0.011820, 0.042940, 0.968881),
    ),
    "tritanopia": (
        (1.255528, -0.076749, -0.178779),
        (-0.078411, 0.930809, 0.147602),
        (0.004733, 0.691367, 0.303900),
    ),
}

SIMULATIONS: tuple[str, ...] = ("normal", "deuteranopia", "protanopia", "tritanopia")
"""The colour visions the map audit checks, normal first."""


def _decode(channel: int) -> float:
    c = channel / 255
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _linear(colour: str) -> tuple[float, float, float]:
    r, g, b = (_decode(c) for c in _channels(colour))
    return (r, g, b)


def _encode(c: float) -> float:
    c = min(1.0, max(0.0, c))
    return 12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055


def _to_hex(rgb: Sequence[float]) -> str:
    return "#" + "".join(f"{round(_encode(c) * 255):02x}" for c in rgb)


def simulate(colour: str, vision: str) -> str:
    """``colour`` (``#rrggbb``) as seen with ``vision``: "normal" or a key of
    :data:`MACHADO_2009`."""
    if vision == "normal":
        return _to_hex(_linear(colour))
    try:
        m = MACHADO_2009[vision]
    except KeyError:
        known = ", ".join(SIMULATIONS)
        raise ValueError(f"unknown colour vision {vision!r}; available: {known}") from None
    rgb = _linear(colour)
    return _to_hex([sum(m[i][j] * rgb[j] for j in range(3)) for i in range(3)])


def to_lab(colour: str) -> tuple[float, float, float]:
    """CIELAB (D65) of an sRGB colour."""
    r, g, b = _linear(colour)
    x = (0.4124564 * r + 0.3575761 * g + 0.1804375 * b) / 0.95047
    y = 0.2126729 * r + 0.7151522 * g + 0.0721750 * b
    z = (0.0193339 * r + 0.1191920 * g + 0.9503041 * b) / 1.08883

    def f(t: float) -> float:
        return t ** (1 / 3) if t > (6 / 29) ** 3 else t / (3 * (6 / 29) ** 2) + 4 / 29

    fx, fy, fz = f(x), f(y), f(z)
    return (116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz))


def ciede2000(lab1: Sequence[float], lab2: Sequence[float]) -> float:
    """The CIEDE2000 difference between two CIELAB colours (kL = kC = kH = 1)."""
    l1, a1, b1 = lab1
    l2, a2, b2 = lab2
    c1 = math.hypot(a1, b1)
    c2 = math.hypot(a2, b2)
    c_bar7 = ((c1 + c2) / 2) ** 7
    g = 0.5 * (1 - math.sqrt(c_bar7 / (c_bar7 + 25**7)))
    a1p, a2p = (1 + g) * a1, (1 + g) * a2
    c1p, c2p = math.hypot(a1p, b1), math.hypot(a2p, b2)

    def hue(b: float, ap: float) -> float:
        if b == 0 and ap == 0:
            return 0.0
        return math.degrees(math.atan2(b, ap)) % 360

    h1p, h2p = hue(b1, a1p), hue(b2, a2p)
    dlp = l2 - l1
    dcp = c2p - c1p
    if c1p * c2p == 0:
        dhp = 0.0
    else:
        dhp = h2p - h1p
        if dhp > 180:
            dhp -= 360
        elif dhp < -180:
            dhp += 360
    dhp_big = 2 * math.sqrt(c1p * c2p) * math.sin(math.radians(dhp) / 2)
    lp_bar = (l1 + l2) / 2
    cp_bar = (c1p + c2p) / 2
    if c1p * c2p == 0:
        hp_bar = h1p + h2p
    elif abs(h1p - h2p) <= 180:
        hp_bar = (h1p + h2p) / 2
    elif h1p + h2p < 360:
        hp_bar = (h1p + h2p + 360) / 2
    else:
        hp_bar = (h1p + h2p - 360) / 2
    t = (
        1
        - 0.17 * math.cos(math.radians(hp_bar - 30))
        + 0.24 * math.cos(math.radians(2 * hp_bar))
        + 0.32 * math.cos(math.radians(3 * hp_bar + 6))
        - 0.20 * math.cos(math.radians(4 * hp_bar - 63))
    )
    d_theta = 30 * math.exp(-(((hp_bar - 275) / 25) ** 2))
    cp_bar7 = cp_bar**7
    r_c = 2 * math.sqrt(cp_bar7 / (cp_bar7 + 25**7))
    s_l = 1 + 0.015 * (lp_bar - 50) ** 2 / math.sqrt(20 + (lp_bar - 50) ** 2)
    s_c = 1 + 0.045 * cp_bar
    s_h = 1 + 0.015 * cp_bar * t
    r_t = -math.sin(math.radians(2 * d_theta)) * r_c
    return math.sqrt(
        (dlp / s_l) ** 2
        + (dcp / s_c) ** 2
        + (dhp_big / s_h) ** 2
        + r_t * (dcp / s_c) * (dhp_big / s_h)
    )


def delta_e(colour1: str, colour2: str, vision: str = "normal") -> float:
    """CIEDE2000 between two sRGB colours as seen with ``vision`` (see :func:`simulate`)."""
    return ciede2000(to_lab(simulate(colour1, vision)), to_lab(simulate(colour2, vision)))


def neighbour_differences(fills: Sequence[str]) -> dict[str, list[float]]:
    """For each of :data:`SIMULATIONS`, the CIEDE2000 between each pair of neighbouring
    fills, rounded to 0.1."""
    return {
        vision: [round(delta_e(a, b, vision), 1) for a, b in itertools.pairwise(fills)]
        for vision in SIMULATIONS
    }
