"""Hausa: sentence templates and the claim checker's vocabulary (new in 0.4).

**Drafted by an AI model (Claude), not reviewed by a native speaker.** Plain Boko spelling
with the hooked letters ɓ ɗ ƙ ƴ and ʼ for the glottal stop. Same keys and placeholders as
:mod:`disability_access_charts._lang.en`; numbers stay as digits with "." as the decimal
point. Differences from English that the checker is told about:

* a counting noun comes before its number ("Ɗigo 37", ``COUNT_BEFORE``), usually in the
  singular, as Hausa does with numerals ("mutum biyar");
* the hedge comes before the superlative ("Ƙiyasi mafi yawa", ``HEDGE_BEFORE``);
* comparisons are verbs: "ya fi" (is more than, ``UP_VERBS``) and "ya gaza" (falls short
  of, ``DOWN_VERBS``);
* "the survey can / cannot show a difference" is "binciken ya iya / ya kasa nuna
  bambanci", which avoids the split negation "ba ... ba";
* ranks use digits: "ƙiyasi na 2 daga sama" (the estimate 2nd from the top).

Wording is genderless where a template does not know its noun's gender ("duk", "duka").
Ratios ("sau biyu") are not recognised. ``MESSAGES`` (problem reports, for developers) and
``MAP_LEGEND`` (the page's English legend) stay English.
"""

from __future__ import annotations

from collections.abc import Sequence

from disability_access_charts._lang import en

CODE = "ha"

FOLD = False
WORD = r"[^\W\d_]+"
CAPITALS = r"\b[^\W\d_]+\b"
ARTICLE = r"(?!)"
HEDGE_BEFORE = r"\bƙiyasi\s+"
UP_VERBS: tuple[str, ...] = ("ya fi",)
COUNT_BEFORE = True
SERIES_NOUNS: tuple[str, ...] = ("jeri",)
LEVEL = r"\bta\s+(\d+(?:\.\d+)?)\s*%"
NOT_NAME = r"(?!)"
UNKNOWN_SUPERLATIVE = ""

GLOSSARY: dict[str, str] = {}

TEMPLATES: dict[str, str] = {
    "kind_bar": "Jadawalin sanduna",
    "kind_dot": "Jadawalin ɗigo",
    "intro_bars": "{kind}: {title}. Sanda {n}, ɗaya ga duk {label}.",
    "intro_bars_ci": (
        "{kind}: {title}. Sanda {n}, ɗaya ga duk {label}, kuma duk suna da {interval}."
    ),
    "intro_dots": "{kind}: {title}. Ɗigo {n}, ɗaya ga duk {label}.",
    "intro_dots_ci": "{kind}: {title}. Ɗigo {n}, ɗaya ga duk {label}, kuma duk suna da {interval}.",
    "intro_series": "{kind}: {title}. Layi {n}, ɗaya ga duk {label}, da jeri {k}: {names}.",
    "intro_series_ci": (
        "{kind}: {title}. Layi {n}, ɗaya ga duk {label}, da jeri {k}: {names}, "
        "kuma duk ƙiyasi yana da {interval}."
    ),
    "intro_series_one": "{kind}: {title}. Layi 1, na {name}, da jeri {k}: {names}.",
    "one_bar": "{kind}: {title}. Sanda 1, ta {clause}.",
    "one_dot": "{kind}: {title}. Ɗigo 1, na {clause}.",
    "series_value": "{series}: {clause}.",
    "series_all_equal": "{series}: duk {things} {n} suna da {value}.",
    "series_highest_ci": "{series}: ƙiyasi mafi yawa shi ne {high}{high_difference}.",
    "clause": "{names}, {each}{value}",
    "each": "duka ",
    "share": " ({share}% na jimilla)",
    "interval_inline": " ({interval} {lower} zuwa {upper})",
    "largest": "Mafi yawa: {clause}.",
    "smallest": "Mafi ƙaranci: {clause}.",
    "highest": "Mafi yawa: {clause}.",
    "lowest": "Mafi ƙaranci: {clause}.",
    "series_extremes": "{series}: mafi yawa shi ne {high}; mafi ƙaranci shi ne {low}.",
    "highest_ci": "Ƙiyasi mafi yawa: {clause}{difference}.",
    "lowest_ci": "Ƙiyasi mafi ƙaranci: {clause}{difference}.",
    "series_extremes_ci": "{series}: ƙiyasi mafi yawa shi ne {high}{high_difference}; "
    "ƙiyasi mafi ƙaranci shi ne {low}{low_difference}.",
    "difference": ", kuma binciken {can} nuna bambanci da {which}, {clause}",
    "can": "ya iya",
    "cannot": "ya kasa",
    "next": "ƙiyasi na gaba",
    "other": "ɗayan ƙiyasin",
    "all_equal": "Duk {things} {n} suna da {value}.",
    "things_bars": "sanda",
    "things_dots": "ɗigo",
    "things_estimates": "ƙiyasi",
    "intervals": "Tazarori ({interval}): {items}.",
    "series_intervals": "{series}, tazarori ({interval}): {items}.",
    "interval_item": "{name} {lower} zuwa {upper}",
    "total": "Jimilla: {total}.",
    "source": "Tushe: {source}.",
}

# The page's legend is English, so its announcements stay English (see en.MAP_LEGEND).
MAP_LEGEND: dict[str, str] = dict(en.MAP_LEGEND)

MAP_TEXT: dict[str, str] = {
    "kind_map": "Taswira",
    "intro_map": "{kind}: {title}. Akwai {noun} {n}.",
    "intro_map_ci": "{kind}: {title}. Akwai {noun} {n}, kuma duk suna da {interval}.",
    "classes": "An raba su zuwa rukuni {k}: {items}.",
    "class_item": "{label}, {noun} {count}",
    "class_under": "Ƙasa da {b}",
    "class_between": "{lo} zuwa ƙasa da {hi}",
    "class_over": "{b} zuwa sama",
}

FINDINGS: dict[str, str] = {
    "series_lowest_ci": "{series}: ƙiyasi mafi ƙaranci shi ne {low}{low_difference}.",
    "finding_item": "{name}, {value}",
    "finding_rank_item": "{name}, {rank} ({value})",
    "rank_top": "ƙiyasi mafi yawa",
    "rank_bottom": "ƙiyasi mafi ƙaranci",
    "rank_high": "ƙiyasi na {ordinal} daga sama",
    "rank_low": "ƙiyasi na {ordinal} daga ƙasa",
    "finding_one": "{prefix}{items}, {direction} {other}.",
    "finding_many": "{prefix}{items}, kowannensu {direction} {other}.",
    "finding_gap": "{name}: {a}, {va}, {direction} {b}, {vb}.",
    "finding_prefix": "{series}: ",
    "higher": "ya fi",
    "lower": "ya gaza",
    "finding_review": ("A karanta da hankali: an yi wa ƙiyasin {name} alama don a sake duba shi."),
    "finding_review_series": (
        "A karanta da hankali: an yi wa ƙiyasin {series} na {name} alama don a sake duba shi."
    ),
    "findings_count": "An duba {comparisons} {checked}, an tabbatar da {supported}.",
    "comparison": "kwatance",
    "comparisons": "kwatance",
    "findings_method": (
        "Ana ɗaukar kwatance a matsayin tabbatacce idan bambancin da ke tsakanin ƙiyasi biyu "
        "ya fi abin da rashin tabbas na binciken ya ba da dama, bayan an yi laʼakari da duk "
        "kwatancen da aka duba (Benjamini-Hochberg, ƙimar gano abin da ba gaskiya ba {q}%). "
        "Waɗannan suna bayyana ƙiyasin ne kawai; ba sa bayyana dalilin bambancinsu."
    ),
    "findings_dropped": (
        "Ba a gwada ƙarin {comparisons} {dropped} ba, saboda akwai ƙiyasin da aka ɓoye, ko "
        "wanda bai da cikakken daidaito, ko wanda tazararsa ba ta da faɗi, a cikin {they}."
    ),
    "findings_withheld": (
        "Ba a nuna ko kwatanta waɗannan ba ({count}): {names}; masu amsa sun yi kaɗan ko "
        "babu bayanai."
    ),
    "findings_none": "Babu ɗaya daga cikin kwatancen da ya tabbata.",
    "they_one": "wannan kwatancen",
    "they_many": "waɗannan kwatancen",
}

AND = "da"


def join(names: Sequence[str]) -> str:
    """'A', 'A da B', 'A, B da C'."""
    names = list(names)
    if len(names) == 1:
        return names[0]
    return ", ".join(names[:-1]) + f" {AND} " + names[-1]


def items(parts: Sequence[str]) -> str:
    """'A, 1%; B, 2%; da C, 3%' (as en.items)."""
    parts = list(parts)
    if len(parts) == 1:
        return parts[0]
    return "; ".join(parts[:-1]) + f"; {AND} " + parts[-1]


def ordinal(n: int) -> str:
    """Ranks are written with digits: 'na 2'."""
    return str(n)


def label(category_label: str) -> str:
    return category_label.lower()


def plural(noun: str, n: int) -> str:
    """Hausa uses the singular with a numeral here ('jiha 37')."""
    del n
    return noun


# --- Claim vocabulary (see en.py for what each list does) -------------------------------

MAX_WORDS: tuple[str, ...] = ("mafi yawa",)
MIN_WORDS: tuple[str, ...] = ("mafi ƙaranci",)
MAX_WORDS_AFTER_THE: tuple[str, ...] = ()
MIN_WORDS_AFTER_THE: tuple[str, ...] = ()
HEDGES: tuple[str, ...] = ("ƙiyasi", "ƙiyasin")

UP_WORDS: tuple[str, ...] = ()
DOWN_WORDS: tuple[str, ...] = ()
THAN = "fiye da"

RATIO_WORDS: dict[str, float] = {"ninki biyu": 2.0, "rabi": 0.5, "ninki uku": 3.0}
DOWN_VERBS: tuple[str, ...] = ("ya gaza",)
TIMES = "sau"
NUMBER_WORDS: dict[str, float] = {
    "biyu": 2,
    "uku": 3,
    "huɗu": 4,
    "biyar": 5,
    "shida": 6,
    "bakwai": 7,
    "takwas": 8,
    "tara": 9,
    "goma": 10,
}

ORDINAL_WORDS: dict[str, int] = {}
RANK_NUMBER_WORDS: dict[str, int] = {"ɗaya": 1, **{k: int(v) for k, v in NUMBER_WORDS.items()}}
RANK_PATTERNS: tuple[str, ...] = (
    r"\bna\s+(?P<rank>\d+)(?:\s+cikin\s+(?P<of>\d+))?\s+daga\s+(?P<dir>sama|ƙasa)\b",
)
ASCENDING_WORDS: tuple[str, ...] = ("ƙasa",)

NEGATORS: tuple[str, ...] = (r"\bba\b", r"\bbai\b", r"\bbabu\b", r"\bkada\b")
QUALIFIERS: tuple[str, ...] = (
    r"\bɗaya\s+daga\s+cikin\b",
    r"\bkusan\b",
    r"\bkamar\b",
    r"\bkunnen\s+doki\b",
)
EQUALITY_BINARY: tuple[str, ...] = (r"daidai\s+da", r"iri\s+ɗaya\s+da")
EQUALITY_PAIR: tuple[str, ...] = (r"(?:sun|suna)\s+daidai",)
NO_DIFFERENCE: tuple[str, ...] = (
    r"\bbabu\s+(?:\w+\s+){0,2}bambanci\b",
    r"\bba\s+(?:\w+\s+){0,2}bambanci\b",
    r"\bba\s+sa\s+bambanta\b",
)
DIFFERENCE = r"\b(?P<modal>ya\s+iya|ya\s+kasa)\s+nuna\s+bambanci\b"
CANNOT: tuple[str, ...] = ("ya kasa",)
BETWEEN = "tsakanin"
FROM = "da"

BREAKS: tuple[str, ...] = (
    r",\s+kuma\b",
    r",\s+amma\b",
    r",\s+yayin\s+da\b",
    r"\bamma\b",
    r"\bya\s+fi\b",
    r"\bya\s+gaza\b",
    r"\bfiye\s+da\b",
)
CONTRASTS: tuple[str, ...] = (r"\bmaimakon\b", r"\bban\s+da\b")
RATIO_QUALIFIERS: tuple[str, ...] = (r"\bfiye\s+da", r"\bkusan", r"\bkimanin", r"\baƙalla")
EXCLUDERS: tuple[str, ...] = (r"\bban\s+da", r"\bba")
STRONG_BREAKS: tuple[str, ...] = (r",\s+kuma\b", r"\bamma\b", r",\s+yayin\s+da\b")
AND_SPLIT_VERBS: tuple[str, ...] = ("ya", "yana", "ta", "tana")
CONNECTOR = r"[\s,]*(?:(?:kuma|amma)\s+)?"
ELLIPSIS = r"\s*(?:kuma\s+)?(?:ya|ta)\s+(?:fi|gaza)\b"
LINK_AFTER_NAME = r"\s*[:,(]?\s*"
IN_NAME = r"\s*%?\s*a\s+"
RANGE_JOIN = r"\s*%?\s*(?:zuwa|–|—)\s*"
RESPECTIVELY = r"\bbi\s+da\s+bi\b"
LIST_SEPARATOR = r"\s*(?:,\s*(?:da\s+|ko\s+)?|da\s+|ko\s+|&\s*)\s*"
ITEM_SEPARATOR = r"\s*,\s*-?\d[\d,]*(?:\.\d+)?\s*%?\s*;\s*(?:(?:da|ko)\s+)?"
LIST_JOINERS = r"\b(?:da|ko)\b|&"

UNCHECKED: tuple[str, ...] = (
    "ƙaru",
    "ya ƙaru",
    "ragu",
    "ya ragu",
    "rinjaye",
    "mafi rinjaye",
    "zarce",
    "ya zarce",
    "kusan",
    "kamar",
    "kimanin",
    "muhimmanci",
    "a baya",
)
UNCHECKED_PATTERNS: tuple[str, ...] = (r"\bkamar\s+yadda\b", r"\baƙalla\b", r"\bhar\s+zuwa\b")
SPELLED_NUMBERS: tuple[str, ...] = (
    "sifili",
    "ɗaya",
    "biyu",
    "uku",
    "huɗu",
    "biyar",
    "shida",
    "bakwai",
    "takwas",
    "tara",
    "goma",
)
SPELLED_VALUES: dict[str, int] = {w: i for i, w in enumerate(SPELLED_NUMBERS)}
STRUCTURAL: tuple[str, ...] = (r"\bɗaya\s+ga\s+duk\b", r"\bjeri\s+\d+:")
COUNT_NOUNS: tuple[str, ...] = (
    "sanda",
    "sanduna",
    "ɗigo",
    "layi",
    "jeri",
    "rukuni",
    "ƙiyasi",
    "abu",
)
LABEL_STANDIN = "abu"
TOTAL_BEFORE = r"\bjimilla\s*(?::|=)?\s*$"
TOTAL_AFTER = r"^\s*(?:gaba\s+ɗaya|a\s+jimilla)\b"
SHARE_AFTER = r"^\s*%\s*na\s+jimilla\b"
NEUTRAL_WORDS: tuple[str, ...] = (
    "da",
    "na",
    "ta",
    "ne",
    "ce",
    "shi",
    "suna",
    "yana",
    "a",
    "ga",
    "duk",
    "duka",
    "zuwa",
    "ƙiyasi",
    "ƙiyasin",
    "tazarori",
    "jimilla",
    "abu",
    "layi",
)
RESERVED_PHRASES: tuple[str, ...] = (
    "daidai da",
    "ɗaya daga cikin",
    "babu bambanci",
    "ban da",
)
NOT_SUPERLATIVE: tuple[str, ...] = ()
SCALES: dict[str, float] = {"dubu": 1e3, "miliyan": 1e6, "biliyan": 1e9}

# Problem reports are for developers: English (see the module docstring).
MESSAGES: dict[str, str] = dict(en.MESSAGES)
