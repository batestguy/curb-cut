"""Tests for scripts/build_map.py against the committed geoBoundaries file and seeds."""

from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "packages" / "transform" / "scripts" / "build_map.py"
spec = importlib.util.spec_from_file_location("build_map", SCRIPT)
assert spec and spec.loader
build_map = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build_map)


@pytest.fixture(scope="module")
def geojson() -> dict:
    return json.loads(build_map.DEFAULT_GEOJSON.read_text(encoding="utf-8"))


def test_all_37_states_get_a_path_keyed_by_iso_code(geojson: dict) -> None:
    doc = build_map.build(geojson, build_map.SEEDS)
    assert len(doc["paths"]) == 37
    assert "NG-FC" in doc["paths"]  # "Abuja Federal Capital Territory" resolved by alias
    assert all(d.startswith("M") and d.endswith("Z") for d in doc["paths"].values())


def test_small_states_get_a_ring_inside_the_viewbox(geojson: dict) -> None:
    doc = build_map.build(geojson, build_map.SEEDS)
    width, height = (float(v) for v in doc["viewBox"].split()[2:])
    assert {"NG-LA", "NG-FC", "NG-AN"} <= set(doc["rings"])
    for cx, cy, r in doc["rings"].values():
        assert r <= cx <= width - r and r <= cy <= height - r


def test_normalise_matches_the_dbt_macro() -> None:
    assert build_map.normalise_state_key("CROSS-RIVER") == "cross river"
    assert build_map.normalise_state_key("Akwa Ibom ") == "akwa ibom"


def test_a_missing_state_fails_the_build(geojson: dict) -> None:
    broken = copy.deepcopy(geojson)
    broken["features"] = [f for f in broken["features"] if f["properties"]["shapeISO"] != "NG-LA"]
    with pytest.raises(ValueError, match="Lagos is missing"):
        build_map.build(broken, build_map.SEEDS)


def test_an_unknown_name_fails_the_build(geojson: dict) -> None:
    broken = copy.deepcopy(geojson)
    broken["features"][0]["properties"]["shapeName"] = "Atlantis"
    with pytest.raises(ValueError, match="no state matches geoBoundaries name 'Atlantis'"):
        build_map.build(broken, build_map.SEEDS)


def test_a_code_mismatch_fails_the_build(geojson: dict) -> None:
    broken = copy.deepcopy(geojson)
    lagos = next(f for f in broken["features"] if f["properties"]["shapeISO"] == "NG-LA")
    lagos["properties"]["shapeISO"] = "NG-OG"
    with pytest.raises(ValueError, match="Lagos: code NG-LA but geoBoundaries says NG-OG"):
        build_map.build(broken, build_map.SEEDS)
