"""Language tables for the alt-text templates and the claim checker. Only English ships."""

from __future__ import annotations

from types import ModuleType

from disability_access_charts._lang import en

LANGUAGES: dict[str, ModuleType] = {"en": en}


def get(lang: str) -> ModuleType:
    """The language table for ``lang``; unknown codes raise ``ValueError``."""
    try:
        return LANGUAGES[lang]
    except KeyError:
        known = ", ".join(sorted(LANGUAGES))
        raise ValueError(f"unknown language {lang!r}; available: {known}") from None
