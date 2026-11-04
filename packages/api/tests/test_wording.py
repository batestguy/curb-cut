"""The API's own words never call the poverty result causal.

Scans every string the API authors (the OpenAPI document, the home page, the response
notes), not the data, with the guard the poverty page and brief use
(``forbidden`` in ``packages/transform/scripts/poverty_text.py``).
"""

from __future__ import annotations

import importlib.util
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from curbcut_api import app as app_module
from fastapi.testclient import TestClient

SCRIPT = Path(__file__).resolve().parents[2] / "transform" / "scripts" / "poverty_text.py"
spec = importlib.util.spec_from_file_location("poverty_text", SCRIPT)
assert spec is not None and spec.loader is not None
poverty_text = importlib.util.module_from_spec(spec)
spec.loader.exec_module(poverty_text)


def strings(node: Any) -> Iterator[str]:
    if isinstance(node, str):
        yield node
    elif isinstance(node, dict):
        for key, value in node.items():
            yield str(key)
            yield from strings(value)
    elif isinstance(node, list):
        for value in node:
            yield from strings(value)


def test_guard_catches_the_phrases() -> None:
    assert poverty_text.forbidden("the effect of disability on poverty")
    assert poverty_text.forbidden("a causal effect")
    assert not poverty_text.forbidden("an adjusted association, not a causal effect")


def test_openapi_and_home_page_wording(client: TestClient) -> None:
    authored = [
        *strings(client.get("/openapi.json").json()),
        client.get("/").text,
        *(v for k, v in vars(app_module).items() if k.isupper() and isinstance(v, str)),
        *strings(app_module.DHS_SOURCE),
        *strings(app_module.JONAPWD_SOURCE),
        *strings(app_module.MPI_SOURCE),
        *strings(app_module.POPULATION_SOURCE),
    ]
    found = {text[:60]: poverty_text.forbidden(text) for text in authored}
    assert {k: v for k, v in found.items() if v} == {}


def test_response_wording(client: TestClient) -> None:
    # The fixture's data strings are neutral, so everything here is the API's own text.
    for path in ("/status", "/states", "/states/akwa-ibom", "/prevalence", "/compare", "/poverty"):
        for text in strings(client.get(path).json()):
            assert poverty_text.forbidden(text) == [], (path, text)
    assert client.get("/poverty").json()["wording"].endswith("not a causal effect.")


def test_dhs_citation_matches_the_export() -> None:
    # app.py repeats export_marts.DHS_CITATION (a script, not a package); drift fails here.
    path = SCRIPT.parent / "export_marts.py"
    export_spec = importlib.util.spec_from_file_location("export_marts", path)
    assert export_spec is not None and export_spec.loader is not None
    export_marts = importlib.util.module_from_spec(export_spec)
    export_spec.loader.exec_module(export_marts)
    assert app_module.DHS_CITATION == export_marts.DHS_CITATION
