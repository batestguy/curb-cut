"""WCAG 2.2 contrast checks for SC 1.4.3 (text) and SC 1.4.11 (non-text)."""

from __future__ import annotations

import re

_HEX = re.compile(r"^#?([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")

TEXT_MIN = 4.5
"""SC 1.4.3 minimum for normal-size text."""
LARGE_TEXT_MIN = 3.0
"""SC 1.4.3 minimum for large text (18pt, or 14pt bold)."""
NON_TEXT_MIN = 3.0
"""SC 1.4.11 minimum for graphical objects such as chart marks."""


def _channels(color: str) -> tuple[int, int, int]:
    match = _HEX.match(color.strip())
    if not match:
        raise ValueError(f"Expected a hex colour like '#1a2b3c' or '#abc', got {color!r}")
    digits = match.group(1)
    if len(digits) == 3:
        digits = "".join(d * 2 for d in digits)
    return int(digits[0:2], 16), int(digits[2:4], 16), int(digits[4:6], 16)


def relative_luminance(color: str) -> float:
    """Relative luminance of an sRGB hex colour, as defined by WCAG 2.2."""

    def linear(channel: int) -> float:
        c = channel / 255
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (linear(c) for c in _channels(color))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(foreground: str, background: str) -> float:
    """Contrast ratio between two hex colours, from 1.0 to 21.0."""
    lighter, darker = sorted(
        (relative_luminance(foreground), relative_luminance(background)), reverse=True
    )
    return (lighter + 0.05) / (darker + 0.05)


def passes_text(foreground: str, background: str, *, large: bool = False) -> bool:
    """Whether text in ``foreground`` on ``background`` meets SC 1.4.3 (AA)."""
    minimum = LARGE_TEXT_MIN if large else TEXT_MIN
    return contrast_ratio(foreground, background) >= minimum


def passes_non_text(foreground: str, background: str) -> bool:
    """Whether a chart mark in ``foreground`` on ``background`` meets SC 1.4.11."""
    return contrast_ratio(foreground, background) >= NON_TEXT_MIN
