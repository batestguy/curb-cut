"""The committed Noto Sans subset covers every Nigerian-language character the site needs
(D29), positions combining marks, and ships with its licence."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = ROOT / "packages" / "transform" / "scripts"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


fonts = _load("make_font_subset")
FONT = fonts.OUT_DIR / fonts.OUT_NAME


def test_subset_covers_every_required_character() -> None:
    font = TTFont(FONT)
    assert font.flavor == "woff2"
    cmap = font.getBestCmap() or {}
    missing = [f"U+{ord(c):04X}" for c in fonts.REQUIRED if ord(c) not in cmap]
    assert missing == []
    for c in "ẹọṣɓɗƙƴịụṅ₦":  # the D29 list, plus the naira sign
        assert ord(c) in cmap


def test_subset_positions_marks_and_keeps_the_weight_axis() -> None:
    font = TTFont(FONT)
    gpos = {r.FeatureTag for r in font["GPOS"].table.FeatureList.FeatureRecord}
    assert {"mark", "mkmk", "kern"} <= gpos
    axes = {a.axisTag: (a.minValue, a.maxValue) for a in font["fvar"].axes}
    assert axes == {"wght": (400, 700)}
    assert FONT.stat().st_size < 60 * 1024


def test_licence_ships_with_the_font() -> None:
    licence = (fonts.OUT_DIR / "OFL.txt").read_text(encoding="utf-8")
    assert "SIL Open Font License, Version 1.1" in licence
