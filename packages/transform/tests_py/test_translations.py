"""Tests for scripts/translations.py and packages/transform/translations.yml (P6 item 8)."""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

import pytest
import yaml
from disability_access_charts import Reference, Series, dot

ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = ROOT / "packages" / "transform" / "scripts"


def _load(name: str):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


tr = _load("translations")
pages = _load("build_state_pages")
charts = _load("build_charts")
ACTIVITIES = [label for _, label in pages.DOMAINS]


def test_the_glossary_has_every_language_for_every_string() -> None:
    g = tr.load(activities=ACTIVITIES)
    assert list(g.names) == ["ha", "yo", "ig", "pcm"]
    for key in tr.STRINGS:
        assert set(g.strings[key]) == {"en", "ha", "yo", "ig", "pcm"}
    for activity in ACTIVITIES:
        assert set(g.activities[activity]) == {"ha", "yo", "ig", "pcm"}


@pytest.mark.parametrize(
    "path",
    [("note", "yo"), ("strings", "map_title", "ig"), ("activities", "Seeing", "pcm")],
)
def test_a_missing_string_fails_the_build(tmp_path: Path, path: tuple[str, ...]) -> None:
    doc = yaml.safe_load(tr.DEFAULT_GLOSSARY.read_text(encoding="utf-8"))
    node = doc
    for key in path[:-1]:
        node = node[key]
    del node[path[-1]]
    bad = tmp_path / "translations.yml"
    bad.write_text(yaml.safe_dump(doc, allow_unicode=True, sort_keys=False), encoding="utf-8")
    with pytest.raises(ValueError, match="missing"):
        tr.load(bad, activities=ACTIVITIES)


def test_an_unknown_activity_fails_the_build() -> None:
    with pytest.raises(ValueError, match="no activity"):
        tr.load(activities=["Juggling"])


def test_the_english_strings_are_the_builders_own() -> None:
    g = tr.load()
    assert g.get("dhs_source", "en") == charts.DHS_SOURCE == pages.DHS_SOURCE
    assert g.get("nigeria_as_a_whole", "en") == charts.NATIONAL_LABEL == pages.NATIONAL_LABEL
    assert g.get("map_title", "en") == "Disability among adults 18+ by state"
    assert g.get("dots_title", "en") == (
        "Disability among adults 18+ by state, with 95% confidence intervals"
    )
    assert g.get("state_title", "en", where="Kano") == (
        "Adults 18+ in Kano with a lot of difficulty or who cannot do it at all, by activity, "
        "with 95% confidence intervals"
    )


def test_the_orthography_uses_each_languages_letters() -> None:
    g = tr.load()
    text = " ".join(g.notes.values())
    for letter in ("ɗ", "ọ", "ẹ", "ṣ", "ị", "ụ"):
        assert letter in text, letter


def doc_with_translations() -> dict:
    g = tr.load(activities=ACTIVITIES)
    return dot(
        ["Kano", "Lagos", "Oyo"],
        [Series("Adults (%)", (6.0, 4.0, 2.0), (5.5, 3.5, 1.5), (6.5, 4.5, 2.5))],
        title="Adults",
        value_label="Adults (%)",
        category_label="State",
        source=charts.DHS_SOURCE,
        findings=True,
        reference=Reference(charts.NATIONAL_LABEL, 3.0, 2.8, 3.2),
        translations=tr.translations(g, title="dots_title", category="state_label", reference=True),
    )


def test_translated_documents_audit_clean() -> None:
    doc = doc_with_translations()
    assert doc["audit"]["passed"] and doc["audit"]["warnings"] == 0
    assert list(doc["alt_text_translations"]) == ["ha", "yo", "ig", "pcm"]


def test_the_disclosure_is_labelled_and_marked_with_lang() -> None:
    doc = doc_with_translations()
    g = tr.load()
    html = tr.disclosure_html(doc, tr.ui_json(g))
    assert html.startswith('<details class="translations"><summary>')
    assert "This description in Hausa, Yorùbá, Igbo and Naijá" in html
    assert html.count('class="translation"') == 4
    for code, name in g.names.items():
        assert f"<strong>{name}</strong>: drafted by AI, not reviewed by a native speaker" in html
        assert html.count(f'lang="{code}"') == 2  # its note and its description
    assert "eSpeak NG" in html and "not been reviewed by a native speaker" in html
    # The texts are the document's, escaped.
    assert re.search(r'<p class="translation-text" lang="yo">Àwòrán àmì: ', html)


def test_the_disclosure_refuses_a_reviewed_or_missing_text() -> None:
    doc = doc_with_translations()
    ui = tr.ui_json(tr.load())
    doc["alt_text_translations"]["ig"]["reviewed"] = True
    with pytest.raises(ValueError, match="marked reviewed"):
        tr.disclosure_html(doc, ui)
    del doc["alt_text_translations"]["ig"]
    with pytest.raises(ValueError, match="no ig translation"):
        tr.disclosure_html(doc, ui)
    assert tr.disclosure_html({"id": "x"}, ui) == ""
