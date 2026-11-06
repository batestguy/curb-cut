"""The site's strings for the chart descriptions in other languages, and their disclosure.

P6 item 8. ``packages/transform/translations.yml`` holds what the site supplies to
``disability_access_charts`` (titles, labels, the source line, activity names and "Nigeria as
a whole") for Hausa, Yoruba, Igbo and Nigerian Pidgin, and the disclosure's own text. The
library builds each description from its templates and audits it.

* :func:`load` reads the file and fails if any language is missing from any string;
* :func:`translations` gives the ``translations=`` argument for one chart;
* :func:`disclosure_html` renders the no-script ``<details>`` under a chart (the state
  pages); ``site/src/translations.js`` builds the same markup in the browser from
  :func:`ui_json` (written by ``build_charts.py`` to ``data/translations.json``) and the
  chart document, for the main page.

Every translated text was drafted by an AI model and has not been reviewed by a native
speaker; the disclosure says so for each language.
"""

from __future__ import annotations

import html
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from disability_access_charts import Translation

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_GLOSSARY = ROOT / "packages" / "transform" / "translations.yml"
LANGS: tuple[str, ...] = ("ha", "yo", "ig", "pcm")
STRINGS: tuple[str, ...] = (
    "interval_label",
    "dhs_source",
    "state_label",
    "activity_label",
    "nigeria_as_a_whole",
    "map_title",
    "dots_title",
    "state_title",
)


@dataclass(frozen=True)
class Glossary:
    names: dict[str, str]  # language code -> its name in English
    summary: str
    note: str
    label: str
    notes: dict[str, str]  # language code -> the note in that language
    strings: dict[str, dict[str, str]]  # key -> {"en": ..., code: ...}
    activities: dict[str, dict[str, str]]  # English activity -> {code: ...}

    def get(self, key: str, lang: str, **fmt: str) -> str:
        return self.strings[key][lang].format(**fmt)


def _text(value: Any, where: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"translations.yml: {where} is missing or empty")
    return " ".join(value.split())


def load(path: Path = DEFAULT_GLOSSARY, activities: Sequence[str] = ()) -> Glossary:
    """Read and check the glossary. Every string, note and activity in ``activities`` must
    have every language (and the strings their English too), or this raises ValueError."""
    doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    names = doc.get("languages") or {}
    if list(names) != list(LANGS):
        raise ValueError(f"translations.yml: languages must be {', '.join(LANGS)} in that order")
    disclosure = doc.get("disclosure") or {}
    notes = doc.get("note") or {}
    strings = doc.get("strings") or {}
    acts = doc.get("activities") or {}
    out_strings: dict[str, dict[str, str]] = {}
    for key in STRINGS:
        entry = strings.get(key) or {}
        out_strings[key] = {
            lang: _text(entry.get(lang), f"{key}.{lang}") for lang in ("en", *LANGS)
        }
    missing = [a for a in activities if a not in acts]
    if missing:
        raise ValueError(f"translations.yml: no activity {', '.join(missing)}")
    out_acts = {
        a: {lang: _text((acts.get(a) or {}).get(lang), f"activities.{a}.{lang}") for lang in LANGS}
        for a in acts
    }
    return Glossary(
        names={lang: _text(names.get(lang), f"languages.{lang}") for lang in LANGS},
        summary=_text(disclosure.get("summary"), "disclosure.summary"),
        note=_text(disclosure.get("note"), "disclosure.note"),
        label=_text(disclosure.get("label"), "disclosure.label"),
        notes={lang: _text(notes.get(lang), f"note.{lang}") for lang in LANGS},
        strings=out_strings,
        activities=out_acts,
    )


def translations(
    g: Glossary,
    *,
    title: str,
    category: str,
    reference: bool = False,
    activities: Sequence[str] = (),
    where: str | None = None,
) -> dict[str, Translation]:
    """The ``translations=`` argument for one chart: ``title`` and ``category`` are keys of
    ``strings`` (``state_title`` takes ``where``), ``reference`` adds "Nigeria as a whole",
    ``activities`` the activity names the chart uses."""
    fmt = {} if where is None else {"where": where}
    out: dict[str, Translation] = {}
    for lang in LANGS:
        names = {a: g.activities[a][lang] for a in activities}
        if reference:
            names[g.get("nigeria_as_a_whole", "en")] = g.get("nigeria_as_a_whole", lang)
        out[lang] = Translation(
            title=g.get(title, lang, **fmt),
            source=g.get("dhs_source", lang),
            category_label=g.get(category, lang),
            interval_label=g.get("interval_label", lang),
            names=names,
        )
    return out


def ui_json(g: Glossary) -> dict[str, Any]:
    """The disclosure's text for the page's script (``data/translations.json``)."""
    return {
        "summary": g.summary,
        "note": g.note,
        "label": g.label,
        "languages": [
            {"code": lang, "name": g.names[lang], "note": g.notes[lang]} for lang in LANGS
        ],
    }


def disclosure_html(doc: Mapping[str, Any], ui: Mapping[str, Any]) -> str:
    """The ``<details>`` under a chart: the English note, then for each language a visible
    label ("Hausa: drafted by AI, ..."), its note and the chart's description, each marked
    with its ``lang``. Works with no script. Empty if the document has no translations."""
    block = doc.get("alt_text_translations") or {}
    if not block:
        return ""
    esc = html.escape
    parts = [
        '<details class="translations">',
        f"<summary>{esc(ui['summary'])}</summary>",
        f'<p class="translations-note">{esc(ui["note"])}</p>',
    ]
    for lang in ui["languages"]:
        entry = block.get(lang["code"])
        if entry is None:
            raise ValueError(f"{doc.get('id')}: no {lang['code']} translation")
        if entry.get("reviewed") is not False:
            # The label says "not reviewed"; a reviewed text needs other words.
            raise ValueError(f"{doc.get('id')}: the {lang['code']} text is marked reviewed")
        code = esc(lang["code"])
        parts += [
            '<div class="translation">',
            f'<p class="translation-label"><strong>{esc(lang["name"])}</strong>: '
            f"{esc(ui['label'])}</p>",
            f'<p class="translation-note" lang="{code}">{esc(lang["note"])}</p>',
            f'<p class="translation-text" lang="{code}">{esc(entry["text"])}</p>',
            "</div>",
        ]
    parts.append("</details>")
    return "".join(parts)
