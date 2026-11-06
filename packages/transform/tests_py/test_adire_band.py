"""The decorative adire band (P6 item 8): the library's tiles, its colours, every page."""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

import pytest
from disability_access_charts.contrast import NON_TEXT_MIN, contrast_ratio
from disability_access_charts.patterns import DOTS, RINGS

ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = ROOT / "packages" / "transform" / "scripts"
STYLE = ROOT / "site" / "src" / "style.css"
BAND = '<div class="adire-band" aria-hidden="true"></div>'
FLAG = '<div class="flag-band" aria-hidden="true"></div>'


def _load(name: str):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


band = _load("adire_band")


def _tokens(scheme: str) -> dict[str, str]:
    css = re.sub(r"/\*.*?\*/", "", STYLE.read_text(encoding="utf-8"), flags=re.S)
    if scheme == "light":
        block = re.search(r"^:root\s*\{(.*?)\}", css, flags=re.S | re.M)
    else:
        block = re.search(
            r"@media\s*\(prefers-color-scheme:\s*dark\)\s*\{\s*:root\s*\{(.*?)\}", css, flags=re.S
        )
    assert block
    return dict(re.findall(r"--([\w-]+)\s*:\s*(#[0-9a-fA-F]{6})\s*;", block.group(1)))


def test_the_band_is_drawn_with_the_librarys_oniko_tiles() -> None:
    svg = band.tile_svg()
    assert RINGS.path in svg and DOTS.path in svg
    css = STYLE.read_text(encoding="utf-8")
    url = band.mask_url()
    assert css.count(f"-webkit-mask: {url} 0 0 / 2rem 1rem repeat;") == 1
    assert css.count(f"mask: {url} 0 0 / 2rem 1rem repeat;") == 2  # the -webkit- line too


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_the_band_meets_3_to_1_in_both_themes(scheme: str) -> None:
    t = _tokens(scheme)
    assert contrast_ratio(t["adire-ink"], t["adire-bg"]) >= NON_TEXT_MIN
    assert contrast_ratio(t["adire-bg"], t["bg"]) >= NON_TEXT_MIN


def test_the_band_is_hidden_in_forced_colours() -> None:
    css = re.sub(r"/\*.*?\*/", "", STYLE.read_text(encoding="utf-8"), flags=re.S)
    assert re.search(
        r"@media\s*\(forced-colors:\s*active\)\s*\{\s*\.adire-band\s*\{\s*display:\s*none;", css
    )


@pytest.mark.parametrize(
    "page",
    ["index.html", "methodology.html", "explorer.html", "sensitivity.html"],
)
def test_every_hand_written_page_has_the_band_after_the_flag(page: str) -> None:
    html = (ROOT / "site" / page).read_text(encoding="utf-8")
    assert re.search(re.escape(FLAG) + r"\s*" + re.escape(BAND), html)


@pytest.mark.parametrize(
    "builder", ["build_state_pages.py", "build_poverty_page.py", "build_data_dictionary.py"]
)
def test_every_page_builder_writes_the_band_after_the_flag(builder: str) -> None:
    source = (SCRIPTS / builder).read_text(encoding="utf-8")
    assert source.count("flag-band") == 1 and source.count("adire-band") == 1
    assert source.index("flag-band") < source.index("adire-band")
