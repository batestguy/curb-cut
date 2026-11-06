"""Chart descriptions in other languages, built from templates and checked (new in 0.4).

``bar``, ``grouped_bar``, ``dot`` and ``choropleth`` take ``translations``: a mapping from a
language code (``ha``, ``yo``, ``ig``, ``pcm``) to a :class:`Translation`, which carries the
strings the caller supplies in that language: the title, the source, the category label,
the interval label and any category, series or reference names (names not given stay as
they are, as Nigeria's state names do). The document then gains an optional field,
``alt_text_translations``::

    {"ha": {"text": "...", "origin": "template", "reviewed": false,
            "inputs": {"title": ..., "source": ..., "category_label": ...,
                       "interval_label": ..., "names": {...}},
            "findings": ["...", ...],   # with a findings block: one per statement
            "classes": "..."}}          # choropleths: the class sentence

Each text is :func:`~disability_access_charts.describe.describe` (or the map's description)
in that language, from the same data, with the same "can / cannot show a difference"
verdicts as the English description. No language model is involved: ``origin`` is
"template". ``reviewed`` is False: the 0.4 tables were drafted by an AI model and have not
been reviewed by a native speaker (``docs/languages.md``). A reviewer who edits a text sets
``origin`` to "human"; the template check is then skipped, and every other check still runs.

The audit (:func:`translation_checks`) runs, for every language:

* ``alt-text-translation-valid`` (error): a known language, the fields above, a name for
  every key in ``inputs.names`` that the data has, and an interval label with the same level
  as the English one;
* ``alt-text-translation-matches-data`` (error): that language's claim checker finds no
  error in the text or the finding sentences; the text has exactly the English
  description's numbers, in the same order; a map's class sentence is the one the data
  gives; and each finding about a "review" estimate carries that language's hedge;
* ``alt-text-translation-unchecked-claims`` (warning): the checker's warnings;
* ``alt-text-translation-matches-template`` (error, ``origin`` "template" only): the text,
  the class sentence and the finding sentences are exactly what the templates give.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from disability_access_charts import _lang
from disability_access_charts.describe import (
    ChartData,
    Verdicts,
    _level_of,
    check_alt_text,
    describe,
    number_tokens,
)

ORIGINS = ("template", "human")


@dataclass(frozen=True)
class Translation:
    """The caller's strings for one language (see the module docstring).

    ``interval_label`` is needed when the chart has intervals; it must state the same level
    as the English one ("tazarar tabbaci ta 95%" for "95% confidence interval"). ``names``
    maps a category, series or reference name (as in the data) to its name in the language.
    """

    title: str
    source: str
    category_label: str
    interval_label: str | None = None
    names: Mapping[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "source": self.source,
            "category_label": self.category_label,
            "interval_label": self.interval_label,
            "names": dict(self.names),
        }

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> Translation:
        return cls(
            title=str(d["title"]),
            source=str(d["source"]),
            category_label=str(d["category_label"]),
            interval_label=None if d.get("interval_label") is None else str(d["interval_label"]),
            names={str(k): str(v) for k, v in dict(d.get("names") or {}).items()},
        )


def _reference_label(doc: Mapping[str, Any]) -> str | None:
    ref = (doc.get("findings") or {}).get("reference")
    return None if not ref else str(ref.get("label"))


def _known_names(doc: Mapping[str, Any], data: ChartData) -> set[str]:
    names = {*data.categories, *(s.name for s in data.series)}
    ref = _reference_label(doc)
    if ref is not None:
        names.add(ref)
    return names


def translated_data(doc: Mapping[str, Any], data: ChartData, t: Translation) -> ChartData:
    """``data`` as the language writes it: the translated labels and names, and the
    translated title and source as its verbatim strings. The numbers are unchanged."""
    unknown = sorted(set(t.names) - _known_names(doc, data))
    if unknown:
        raise ValueError(f"translated names not in the data: {', '.join(unknown)}")
    if data.has_interval:
        if not t.interval_label:
            raise ValueError("the chart has intervals: give the translated interval_label")
        # An unstated level is read as 95%, as the interval test does (describe._z_level).
        if (_level_of(t.interval_label) or 95.0) != (_level_of(data.interval_label) or 95.0):
            raise ValueError(
                f"interval label {t.interval_label!r} does not state the same level as "
                f"{data.interval_label!r}"
            )
    glossary = dict(data.glossary)
    glossary.update({k: v for k, v in t.names.items() if v != k})
    return dataclasses.replace(
        data,
        category_label=t.category_label,
        interval_label=t.interval_label or data.interval_label,
        verbatim=(t.title, t.source),
        glossary=glossary,
    )


def _verdicts(doc: Mapping[str, Any], data: ChartData) -> Verdicts | None:
    from disability_access_charts.findings import extreme_verdicts

    block = doc.get("findings")
    return extreme_verdicts(block, data) if isinstance(block, Mapping) else None


def _findings_texts(doc: Mapping[str, Any], data_t: ChartData, lang: str) -> list[str] | None:
    from disability_access_charts.findings import DEFAULT_Q, Reference, statistical_findings

    block = doc.get("findings")
    if not isinstance(block, Mapping):
        return None
    ref = block.get("reference")
    out = statistical_findings(
        data_t,
        reference=Reference.from_dict(ref) if ref else None,
        withheld=list(block.get("withheld", [])),
        q=float((block.get("method") or {}).get("q", DEFAULT_Q)),
        lang=lang,
    )
    return [s["text"] for s in out["statements"]]


def _is_map(doc: Mapping[str, Any]) -> bool:
    return (doc.get("meta") or {}).get("chart_type") == "choropleth"


def _generate(doc: Mapping[str, Any], data: ChartData, lang: str, t: Translation) -> dict:
    """The template text (and class sentence, finding sentences) for one language."""
    data_t = translated_data(doc, data, t)
    entry: dict[str, Any] = {}
    if _is_map(doc):
        from disability_access_charts.maps import _alt_text, class_labels

        labels = class_labels(list(doc.get("breaks", [])), data.unit, lang)
        classes = [
            {"label": lab, "count": c.get("count")}
            for lab, c in zip(labels, doc.get("classes", []), strict=True)
        ]
        text, sentence, _ = _alt_text(data_t, classes, title=t.title, source=t.source, lang=lang)
        entry["text"] = text
        entry["classes"] = sentence
    else:
        chart_type = str((doc.get("meta") or {}).get("chart_type", "bar"))
        entry["text"] = describe(
            data_t,
            chart_type=chart_type,
            title=t.title,
            source=t.source,
            lang=lang,
            verdicts=_verdicts(doc, data),
        )
    findings = _findings_texts(doc, data_t, lang)
    if findings is not None:
        entry["findings"] = findings
    return entry


def translate(
    doc: Mapping[str, Any], translations: Mapping[str, Translation]
) -> dict[str, dict[str, Any]]:
    """The ``alt_text_translations`` block for ``doc`` (a chart or choropleth document with
    its ``data``, ``findings`` and ``classes`` already in place)."""
    data = ChartData.from_dict(doc["data"])
    base = str((doc.get("meta") or {}).get("alt_text_lang", "en"))
    out: dict[str, dict[str, Any]] = {}
    for lang, t in translations.items():
        _lang.get(lang)
        if lang == base:
            raise ValueError(f"{lang!r} is the document's own language")
        entry = _generate(doc, data, lang, t)
        out[lang] = {
            "text": entry["text"],
            "origin": "template",
            "reviewed": False,
            "inputs": t.to_dict(),
            **{k: entry[k] for k in ("findings", "classes") if k in entry},
        }
    return out


# --- Audit -----------------------------------------------------------------------------


def _check(
    check_id: str, lang: str, severity: str, description: str, passed: bool, **extra: Any
) -> dict[str, Any]:
    return {
        "id": check_id,
        "wcag": "1.1.1",
        "severity": severity,
        "lang": lang,
        "description": description,
        "passed": passed,
        **extra,
    }


def _english_numbers(doc: Mapping[str, Any], data: ChartData) -> list[str]:
    base = str((doc.get("meta") or {}).get("alt_text_lang", "en"))
    return number_tokens(str(doc.get("alt_text") or ""), data, lang=base)


def _statement_data(doc: Mapping[str, Any], data_t: ChartData, family: str) -> ChartData:
    from disability_access_charts.findings import Reference, _with_reference

    ref = (doc.get("findings") or {}).get("reference")
    if family == "outliers" and ref:
        reference = Reference.from_dict(ref)
        return _with_reference(data_t, reference, reference.per_series(len(data_t.series)))
    return data_t


def _one_language(doc: Mapping[str, Any], data: ChartData, lang: str, entry: Any) -> list[dict]:
    from disability_access_charts.findings import HEDGED_FLAGS, hedge_present

    checks: list[dict[str, Any]] = []
    problems: list[str] = []
    data_t: ChartData | None = None
    t: Translation | None = None
    if lang not in _lang.LANGUAGES:
        problems.append(f"unknown language {lang!r}")
    elif not isinstance(entry, Mapping):
        problems.append("the entry is not an object")
    else:
        if not isinstance(entry.get("text"), str) or not entry["text"].strip():
            problems.append("no text")
        if entry.get("origin") not in ORIGINS:
            problems.append(f"origin must be one of {', '.join(ORIGINS)}")
        if not isinstance(entry.get("reviewed"), bool):
            problems.append("reviewed must be true or false")
        try:
            t = Translation.from_dict(entry.get("inputs") or {})
            data_t = translated_data(doc, data, t)
        except (KeyError, TypeError, ValueError) as exc:
            problems.append(f"the inputs cannot be used: {exc}")
        if _is_map(doc) and not isinstance(entry.get("classes"), str):
            problems.append("a map translation needs its class sentence")
        if isinstance(doc.get("findings"), Mapping) and not isinstance(entry.get("findings"), list):
            problems.append("the document has findings: the translation needs its sentences")
    checks.append(
        _check(
            "alt-text-translation-valid",
            lang,
            "error",
            "The translated description names its language, origin and review status, and its "
            "inputs fit the data",
            not problems,
            problems=problems,
        )
    )
    if problems or data_t is None or t is None or not isinstance(entry, Mapping):
        return checks

    text = str(entry["text"])
    verdicts = _verdicts(doc, data)
    errs: list[dict[str, Any]] = []
    warns: list[dict[str, Any]] = []
    mismatch: list[str] = []
    checked = text
    if _is_map(doc):
        from disability_access_charts.maps import _class_sentence, class_labels

        sentence = str(entry["classes"])
        labels = class_labels(list(doc.get("breaks", [])), data.unit, lang)
        want = _class_sentence(
            [
                {"label": lab, "count": c.get("count")}
                for lab, c in zip(labels, doc["classes"], strict=False)
            ],
            _lang.get(lang).label(data_t.category_label),
            lang,
        )
        if sentence != want or sentence not in text:
            mismatch.append("the class sentence is not the one the data gives, or not in the text")
        checked = text.replace(sentence, "", 1).replace("  ", " ")
    for p in check_alt_text(checked, data_t, lang=lang, verdicts=verdicts):
        (errs if p.severity == "error" else warns).append(p.to_dict())
    got = number_tokens(text, data_t, lang=lang)
    want_numbers = _english_numbers(doc, data)
    if got != want_numbers:
        mismatch.append(
            f"its numbers ({', '.join(got)}) differ from the English description's "
            f"({', '.join(want_numbers)})"
        )
    block = doc.get("findings")
    if isinstance(block, Mapping):
        statements = list(block.get("statements", []))
        comparisons = list(block.get("comparisons", []))
        sentences = list(entry.get("findings") or [])
        if len(sentences) != len(statements):
            mismatch.append(
                f"{len(sentences)} finding sentences for {len(statements)} English statements"
            )
        allow = any(c.get("id") == "independence" for c in block.get("caveats", []))
        for st, sentence in zip(statements, sentences, strict=False):
            use = _statement_data(doc, data_t, str(st.get("family")))
            for p in check_alt_text(str(sentence), use, lang=lang):
                if p.severity == "error":
                    errs.append(p.to_dict())
                elif not (p.kind == "independence" and allow):
                    warns.append(p.to_dict())
            for k in st.get("comparisons", []):
                if not (isinstance(k, int) and 0 <= k < len(comparisons)):
                    continue
                for side in ("a", "b"):
                    cell = comparisons[k].get(side) or {}
                    if cell.get("precision") in HEDGED_FLAGS and not hedge_present(
                        str(sentence), cell, data_t, lang
                    ):
                        mismatch.append(f"the finding about {cell.get('category')} is not hedged")
    checks.append(
        _check(
            "alt-text-translation-matches-data",
            lang,
            "error",
            "No number or recognised claim in the translated description (or its finding "
            "sentences) contradicts the data, and it has the English description's numbers",
            not errs and not mismatch,
            problems=[*mismatch, *(p["reason"] for p in errs)],
            claim_problems=errs,
        )
    )
    checks.append(
        _check(
            "alt-text-translation-unchecked-claims",
            lang,
            "warning",
            "Claims in the translated description that its claim checker could not test",
            not warns,
            problems=warns,
        )
    )
    if entry.get("origin") == "template":
        want = _generate(doc, data, lang, t)
        differ = [
            k for k in ("text", "classes", "findings") if k in want and entry.get(k) != want[k]
        ]
        checks.append(
            _check(
                "alt-text-translation-matches-template",
                lang,
                "error",
                "A template translation is exactly what the language's templates give for the data",
                not differ,
                problems=[f"{k} differs from the template's" for k in differ],
            )
        )
    return checks


def translation_checks(doc: Mapping[str, Any]) -> list[dict[str, Any]]:
    """The audit's checks of a document's ``alt_text_translations`` (see the module
    docstring); none when the document has none."""
    block = doc.get("alt_text_translations")
    if block is None:
        return []
    if not isinstance(block, Mapping) or "data" not in doc:
        return [
            _check(
                "alt-text-translation-valid",
                "",
                "error",
                "The translations block is an object keyed by language, on a document with data",
                False,
            )
        ]
    data = ChartData.from_dict(doc["data"])
    checks: list[dict[str, Any]] = []
    for lang, entry in block.items():
        checks += _one_language(doc, data, str(lang), entry)
    return checks


def languages(doc: Mapping[str, Any]) -> Sequence[str]:
    """The languages a document has translations for, in its order."""
    return list((doc.get("alt_text_translations") or {}).keys())
