"""Language tables for the alt-text templates and the claim checker.

English (``en``) is the source language. Hausa (``ha``), Yoruba (``yo``), Igbo (``ig``) and
Nigerian Pidgin (``pcm``, Naijá) were added in 0.4. Their sentences were drafted by an AI
model (Claude) and have **not been reviewed by a native speaker**; see
``docs/languages.md``. Every table has the same keys and placeholders as ``en``.
"""

from __future__ import annotations

import functools
import unicodedata
from types import ModuleType

from disability_access_charts._lang import en, ha, ig, pcm, yo

LANGUAGES: dict[str, ModuleType] = {"en": en, "ha": ha, "yo": yo, "ig": ig, "pcm": pcm}

NAMES: dict[str, str] = {
    "en": "English",
    "ha": "Hausa",
    "yo": "Yorùbá",
    "ig": "Igbo",
    "pcm": "Naijá (Nigerian Pidgin)",
}
"""Each language's name as the site writes it in English."""


def get(lang: str) -> ModuleType:
    """The language table for ``lang``; unknown codes raise ``ValueError``."""
    try:
        return LANGUAGES[lang]
    except KeyError:
        known = ", ".join(sorted(LANGUAGES))
        raise ValueError(f"unknown language {lang!r}; available: {known}") from None


def fold(text: str) -> str:
    """``text`` without combining marks (tone marks, dots below), in NFC.

    The claim checker of a language with ``FOLD = True`` reads folded text and a folded
    vocabulary, so a word such as "pọ̀" (o with a dot below and a grave accent, which has no
    single code point) is one regex word: Python's ``\\b`` treats a combining mark as a
    non-word character. Letters that are not built from a base letter and a mark (Hausa
    ɓ ɗ ƙ ƴ and ʼ) are kept.
    """
    decomposed = unicodedata.normalize("NFD", text)
    kept = "".join(c for c in decomposed if unicodedata.category(c) != "Mn")
    return unicodedata.normalize("NFC", kept)


def _fold_value(value: object) -> object:
    if isinstance(value, str):
        return fold(value)
    if isinstance(value, tuple):
        return tuple(_fold_value(v) for v in value)
    if isinstance(value, dict):
        return {(fold(k) if isinstance(k, str) else k): _fold_value(v) for k, v in value.items()}
    return value


@functools.cache
def checker(lang: str) -> ModuleType:
    """The table the claim checker reads for ``lang``: the table itself, or (``FOLD = True``)
    a copy with every string, word list and template folded (see :func:`fold`). Functions
    (``join``, ``label``, ...) are the table's own."""
    module = get(lang)
    if not getattr(module, "FOLD", False):
        return module
    view = ModuleType(f"{module.__name__}.folded")
    for name in dir(module):
        if not name.startswith("__"):
            setattr(view, name, _fold_value(getattr(module, name)))
    return view
