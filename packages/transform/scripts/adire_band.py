"""The decorative adire band under the flag band (P6 item 8, "Look"; D31).

Abstract rings and dots after adire oniko (Yoruba tie-resist cloth), drawn with the chart
library's own tiles (``disability_access_charts.patterns.RINGS`` and ``DOTS``), so the band
and the map's patterns are the same shapes. Never nsibidi or Ukara signs. One tile of the
band is a ring then two dots, 24 by 12 units.

``site/src/style.css`` uses :func:`mask_url` as the CSS mask of ``.adire-band::before``: the
mask gives the shapes, and the theme's ``--adire-ink`` gives their colour over the band's
``--adire-bg`` (white rings on indigo, as resist-dyed cloth). Run this file to print the
url() for the stylesheet; ``tests_py/test_adire_band.py`` checks the stylesheet holds exactly
this url, that the colours meet 3:1 (WCAG 2.2 SC 1.4.11) in both themes, and that every page
with the flag band has the adire band.
"""

from __future__ import annotations

from urllib.parse import quote

from disability_access_charts.patterns import DOTS, RINGS, TILE

WIDTH = 2 * TILE
HEIGHT = TILE


def tile_svg() -> str:
    """The band's tile: the library's ring tile, then its dots tile, side by side."""
    return (
        f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 {WIDTH} {HEIGHT}'>"
        f"<path d='{RINGS.path}'/>"
        f"<path transform='translate({TILE} 0)' d='{DOTS.path}'/>"
        "</svg>"
    )


def mask_url() -> str:
    """The tile as a CSS url() with a data URI (only the characters CSS needs encoded)."""
    return 'url("data:image/svg+xml,' + quote(tile_svg(), safe=" /=':,.-") + '")'


if __name__ == "__main__":
    print(mask_url())
