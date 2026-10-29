"""The site's colour tokens and the map themes must match the chart library's DEFAULT_THEMES.

The page background is the chart background, and the site's --flag-green / --highlight are the
theme's mark / highlight (see the comment at the top of site/src/style.css). These tests read
the real CSS, so changing one side without the other fails here.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from disability_access_charts.maps import MAP_THEMES
from disability_access_charts.palettes import DEFAULT_THEMES

ROOT = Path(__file__).resolve().parents[3]
STYLE = ROOT / "site" / "src" / "style.css"


def _blocks() -> dict[str, str]:
    """The light :root block and the dark one inside @media (prefers-color-scheme: dark)."""
    css = re.sub(r"/\*.*?\*/", "", STYLE.read_text(encoding="utf-8"), flags=re.S)
    light = re.search(r"^:root\s*\{(.*?)\}", css, flags=re.S | re.M)
    dark = re.search(
        r"@media\s*\(prefers-color-scheme:\s*dark\)\s*\{\s*:root\s*\{(.*?)\}", css, flags=re.S
    )
    assert light and dark, "could not find the light and dark :root blocks in style.css"
    return {"light": light.group(1), "dark": dark.group(1)}


def _token(block: str, name: str) -> str:
    found = re.findall(rf"--{name}\s*:\s*(#[0-9a-fA-F]{{3,8}})\s*;", block)
    assert len(found) == 1, f"--{name} should be set once, found {found}"
    return found[0].lower()


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_site_tokens_equal_default_themes(scheme: str) -> None:
    block = _blocks()[scheme]
    theme = DEFAULT_THEMES[scheme]
    assert _token(block, "flag-green") == theme.mark.lower()
    assert theme.highlight is not None
    assert _token(block, "highlight") == theme.highlight.lower()
    assert _token(block, "bg") == theme.background.lower()
    assert _token(block, "text") == theme.text.lower()


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_map_themes_equal_default_themes(scheme: str) -> None:
    assert MAP_THEMES[scheme].background.lower() == DEFAULT_THEMES[scheme].background.lower()
    assert MAP_THEMES[scheme].text.lower() == DEFAULT_THEMES[scheme].text.lower()
