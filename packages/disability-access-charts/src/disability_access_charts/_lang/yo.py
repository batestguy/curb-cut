"""Yoruba: sentence templates and the claim checker's vocabulary (new in 0.4).

**Drafted by an AI model (Claude), not reviewed by a native speaker.** Standard
orthography with tone marks and dots below (ẹ ọ ṣ). Same keys and placeholders as
:mod:`disability_access_charts._lang.en`; numbers stay as digits with "." as the decimal
point. ``FOLD = True``: the checker reads the text and this table without combining marks
(``_lang.fold``), because a letter such as "ọ̀" has no single code point. Differences from
English that the checker is told about:

* a counting noun comes before its number ("Àmì 37", ``COUNT_BEFORE``);
* the hedge comes before the superlative ("Ìfojúbù tó ga jùlọ", the estimate that is
  highest; ``HEDGE_BEFORE``);
* comparisons are the verbs "ga ju ... lọ" (higher than) and "kéré ju ... lọ" (lower than);
* ranks use digits: "ìfojúbù tó wà ní ipò 2 láti òkè" (the estimate in position 2 from the
  top).

Ratios ("ìlọ́po méjì") are not recognised. ``MESSAGES`` and ``MAP_LEGEND`` stay English.
"""

from __future__ import annotations

from collections.abc import Sequence

from disability_access_charts._lang import en

CODE = "yo"

FOLD = True
WORD = r"[^\W\d_]+"
CAPITALS = r"\b[^\W\d_]+\b"
ARTICLE = r"(?!)"
HEDGE_BEFORE = r"\bìfojúbù\s+(?:tó\s+(?:wà\s+ní\s+)?)?"
UP_VERBS: tuple[str, ...] = ("ga ju",)
COUNT_BEFORE = True
SERIES_NOUNS: tuple[str, ...] = ("ọ̀wọ́",)
LEVEL = r"ìgbẹ́kẹ̀lé\s+(\d+(?:\.\d+)?)\s*%"
NOT_NAME = r"(?!)"
UNKNOWN_SUPERLATIVE = ""

GLOSSARY: dict[str, str] = {}

TEMPLATES: dict[str, str] = {
    "kind_bar": "Àwòrán ọ̀pá",
    "kind_dot": "Àwòrán àmì",
    "intro_bars": "{kind}: {title}. Ọ̀pá {n}, ọ̀kan fún {label} kọ̀ọ̀kan.",
    "intro_bars_ci": (
        "{kind}: {title}. Ọ̀pá {n}, ọ̀kan fún {label} kọ̀ọ̀kan, ọ̀kọ̀ọ̀kan pẹ̀lú {interval} tirẹ̀."
    ),
    "intro_dots": "{kind}: {title}. Àmì {n}, ọ̀kan fún {label} kọ̀ọ̀kan.",
    "intro_dots_ci": (
        "{kind}: {title}. Àmì {n}, ọ̀kan fún {label} kọ̀ọ̀kan, ọ̀kọ̀ọ̀kan pẹ̀lú {interval} tirẹ̀."
    ),
    "intro_series": "{kind}: {title}. Ìlà {n}, ọ̀kan fún {label} kọ̀ọ̀kan, pẹ̀lú ọ̀wọ́ {k}: {names}.",
    "intro_series_ci": (
        "{kind}: {title}. Ìlà {n}, ọ̀kan fún {label} kọ̀ọ̀kan, pẹ̀lú ọ̀wọ́ {k}: {names}, "
        "ìfojúbù kọ̀ọ̀kan pẹ̀lú {interval} tirẹ̀."
    ),
    "intro_series_one": "{kind}: {title}. Ìlà 1, fún {name}, pẹ̀lú ọ̀wọ́ {k}: {names}.",
    "one_bar": "{kind}: {title}. Ọ̀pá 1, fún {clause}.",
    "one_dot": "{kind}: {title}. Àmì 1, fún {clause}.",
    "series_value": "{series}: {clause}.",
    "series_all_equal": "{series}: gbogbo {things} {n} jẹ́ {value}.",
    "series_highest_ci": "{series}: ìfojúbù tó ga jùlọ ni {high}{high_difference}.",
    "clause": "{names}, {each}{value}",
    "each": "ọ̀kọ̀ọ̀kan ",
    "share": " ({share}% nínú àpapọ̀)",
    "interval_inline": " ({interval} {lower} sí {upper})",
    "largest": "Èyí tó pọ̀ jùlọ: {clause}.",
    "smallest": "Èyí tó kéré jùlọ: {clause}.",
    "highest": "Èyí tó ga jùlọ: {clause}.",
    "lowest": "Èyí tó kéré jùlọ: {clause}.",
    "series_extremes": "{series}: èyí tó ga jùlọ ni {high}; èyí tó kéré jùlọ ni {low}.",
    "highest_ci": "Ìfojúbù tó ga jùlọ: {clause}{difference}.",
    "lowest_ci": "Ìfojúbù tó kéré jùlọ: {clause}{difference}.",
    "series_extremes_ci": "{series}: ìfojúbù tó ga jùlọ ni {high}{high_difference}; "
    "ìfojúbù tó kéré jùlọ ni {low}{low_difference}.",
    "difference": ", àti pé ìwádìí náà {can} fi ìyàtọ̀ hàn pẹ̀lú {which}, {clause}",
    "can": "lè",
    "cannot": "kò lè",
    "next": "ìfojúbù tó kàn",
    "other": "ìfojúbù yòókù",
    "all_equal": "Gbogbo {things} {n} jẹ́ {value}.",
    "things_bars": "ọ̀pá",
    "things_dots": "àmì",
    "things_estimates": "ìfojúbù",
    "intervals": "Àwọn ààlà ({interval}): {items}.",
    "series_intervals": "{series}, àwọn ààlà ({interval}): {items}.",
    "interval_item": "{name} {lower} sí {upper}",
    "total": "Àpapọ̀: {total}.",
    "source": "Orísun: {source}.",
}

MAP_LEGEND: dict[str, str] = dict(en.MAP_LEGEND)

MAP_TEXT: dict[str, str] = {
    "kind_map": "Àwòrán ilẹ̀",
    "intro_map": "{kind}: {title}. Ó ní {noun} {n}.",
    "intro_map_ci": "{kind}: {title}. Ó ní {noun} {n}, ọ̀kọ̀ọ̀kan pẹ̀lú {interval} tirẹ̀.",
    "classes": "A pín wọn sí ìsọ̀rí {k}: {items}.",
    "class_item": "{label}, {noun} {count}",
    "class_under": "Kò tó {b}",
    "class_between": "láti {lo} títí dé ìsàlẹ̀ {hi}",
    "class_over": "{b} sókè",
}

FINDINGS: dict[str, str] = {
    "series_lowest_ci": "{series}: ìfojúbù tó kéré jùlọ ni {low}{low_difference}.",
    "finding_item": "{name}, {value}",
    "finding_rank_item": "{name}, {rank} ({value})",
    "rank_top": "ìfojúbù tó ga jùlọ",
    "rank_bottom": "ìfojúbù tó kéré jùlọ",
    "rank_high": "ìfojúbù tó wà ní ipò {ordinal} láti òkè",
    "rank_low": "ìfojúbù tó wà ní ipò {ordinal} láti ìsàlẹ̀",
    "finding_one": "{prefix}{items}, {direction} {other} lọ.",
    "finding_many": "{prefix}{items}, ọ̀kọ̀ọ̀kan wọn {direction} {other} lọ.",
    "finding_gap": "{name}: {a}, {va}, {direction} {b}, {vb} lọ.",
    "finding_prefix": "{series}: ",
    "higher": "ga ju",
    "lower": "kéré ju",
    "finding_review": "Ẹ kà á pẹ̀lú ìṣọ́ra: a ti sàmì sí ìfojúbù {name} fún àyẹ̀wò síi.",
    "finding_review_series": (
        "Ẹ kà á pẹ̀lú ìṣọ́ra: a ti sàmì sí ìfojúbù {series} fún {name} fún àyẹ̀wò síi."
    ),
    "findings_count": "A ṣàyẹ̀wò {comparisons} {checked}; {supported} ní ẹ̀rí tó dájú.",
    "comparison": "ìfiwéra",
    "comparisons": "ìfiwéra",
    "findings_method": (
        "Ìfiwéra kan ní ẹ̀rí nígbà tí ìyàtọ̀ tó wà láàárín ìfojúbù méjì bá tóbi ju ohun tí "
        "àìdánilójú ìwádìí náà fàyè gbà, lẹ́yìn tí a ti ka gbogbo ìfiwéra tí a ṣàyẹ̀wò sí "
        "(Benjamini-Hochberg, ìwọ̀n àwárí èké {q}%). Àwọn wọ̀nyí ń ṣàpèjúwe àwọn ìfojúbù "
        "nìkan; wọn kò sọ ìdí tí wọ́n fi yàtọ̀."
    ),
    "findings_dropped": (
        "A kò dán {comparisons} {dropped} mìíràn wò, nítorí pé {they} ní ìfojúbù kan tí a fi "
        "pamọ́, tí kò péye tó, tàbí tí ààlà rẹ̀ kò fẹ̀ rárá."
    ),
    "findings_withheld": (
        "A kò fi wọ́n hàn, a kò sì fi wọ́n wéra ({count}): {names}; àwọn tó dáhùn kò pọ̀ tó "
        "tàbí kò sí dátà."
    ),
    "findings_none": "Kò sí ìkankan nínú àwọn ìfiwéra tó ní ẹ̀rí.",
    "they_one": "ó",
    "they_many": "wọ́n",
}

AND = "àti"


def join(names: Sequence[str]) -> str:
    """'A', 'A àti B', 'A, B àti C'."""
    names = list(names)
    if len(names) == 1:
        return names[0]
    return ", ".join(names[:-1]) + f" {AND} " + names[-1]


def items(parts: Sequence[str]) -> str:
    """'A, 1%; B, 2%; àti C, 3%' (as en.items)."""
    parts = list(parts)
    if len(parts) == 1:
        return parts[0]
    return "; ".join(parts[:-1]) + f"; {AND} " + parts[-1]


def ordinal(n: int) -> str:
    """Ranks are written with digits: 'ipò 2'."""
    return str(n)


def label(category_label: str) -> str:
    return category_label.lower()


def plural(noun: str, n: int) -> str:
    """Yoruba nouns do not change for the plural ('ìpínlẹ̀ 37')."""
    del n
    return noun


# --- Claim vocabulary (see en.py for what each list does) -------------------------------

MAX_WORDS: tuple[str, ...] = ("ga jùlọ", "pọ̀ jùlọ")
MIN_WORDS: tuple[str, ...] = ("kéré jùlọ",)
MAX_WORDS_AFTER_THE: tuple[str, ...] = ()
MIN_WORDS_AFTER_THE: tuple[str, ...] = ()
HEDGES: tuple[str, ...] = ("ìfojúbù",)

UP_WORDS: tuple[str, ...] = ()
DOWN_WORDS: tuple[str, ...] = ()
THAN = "ju"

RATIO_WORDS: dict[str, float] = {"ìlọ́po méjì": 2.0, "ìdajì": 0.5, "ìlọ́po mẹ́ta": 3.0}
DOWN_VERBS: tuple[str, ...] = ("kéré ju",)
TIMES = "ìlọ́po"
NUMBER_WORDS: dict[str, float] = {
    "méjì": 2,
    "mẹ́ta": 3,
    "mẹ́rin": 4,
    "márùn-ún": 5,
    "mẹ́fà": 6,
    "méje": 7,
    "mẹ́jọ": 8,
    "mẹ́sàn-án": 9,
    "mẹ́wàá": 10,
}

ORDINAL_WORDS: dict[str, int] = {}
RANK_NUMBER_WORDS: dict[str, int] = {"ọ̀kan": 1, **{k: int(v) for k, v in NUMBER_WORDS.items()}}
RANK_PATTERNS: tuple[str, ...] = (
    r"\bipò\s+(?P<rank>\d+)(?:\s+nínú\s+(?P<of>\d+))?\s+láti\s+(?P<dir>òkè|ìsàlẹ̀)\b",
)
ASCENDING_WORDS: tuple[str, ...] = ("ìsàlẹ̀",)

NEGATORS: tuple[str, ...] = (r"\bkò\b", r"\bkọ́\b", r"\bkìí\b", r"\bláìsí\b")
QUALIFIERS: tuple[str, ...] = (r"\bọ̀kan\s+nínú\b", r"\bfẹ́rẹ̀\b", r"\bbíi\b")
EQUALITY_BINARY: tuple[str, ...] = (r"bákan\s+náà\s+pẹ̀lú", r"dọ́gba\s+pẹ̀lú")
EQUALITY_PAIR: tuple[str, ...] = (r"(?:jẹ́\s+)?dọ́gba",)
NO_DIFFERENCE: tuple[str, ...] = (
    r"\bkò\s+sí\s+ìyàtọ̀\b",
    r"\bkò\s+yàtọ̀\b",
    r"\bkò\s+ní\s+ìyàtọ̀\b",
)
DIFFERENCE = r"\b(?P<modal>kò\s+lè|lè)\s+fi\s+ìyàtọ̀\s+hàn\b"
CANNOT: tuple[str, ...] = ("kò lè",)
BETWEEN = "láàárín"
FROM = "pẹ̀lú"

BREAKS: tuple[str, ...] = (
    r",\s+àti\s+pé\b",
    r",\s+àti\b",
    r",\s+ṣùgbọ́n\b",
    r"\bṣùgbọ́n\b",
    r"\bnígbà\s+tí\b",
    r"\bga\s+ju\b",
    r"\bkéré\s+ju\b",
    r"\bju\b",
)
CONTRASTS: tuple[str, ...] = (r"\bdípò\b", r"\byàtọ̀\s+sí\b")
RATIO_QUALIFIERS: tuple[str, ...] = (r"\bju", r"\bfẹ́rẹ̀", r"\bnǹkan\s+bí", r"\bó\s+kéré\s+tán")
EXCLUDERS: tuple[str, ...] = (r"\byàtọ̀\s+sí", r"\bkì\s+í\s+ṣe")
STRONG_BREAKS: tuple[str, ...] = (r",\s+àti\b", r"\bṣùgbọ́n\b", r"\bnígbà\s+tí\b")
AND_SPLIT_VERBS: tuple[str, ...] = ()
CONNECTOR = r"[\s,]*(?:(?:àti|ṣùgbọ́n)\s+)?(?:ó\s+)?"
ELLIPSIS = r"\s*(?:ó\s+)?(?:ga|kéré)\s+ju\b"
LINK_AFTER_NAME = r"\s*[:,(]?\s*"
IN_NAME = r"\s*%?\s*ní\s+"
RANGE_JOIN = r"\s*%?\s*(?:sí|–|—)\s*"
RESPECTIVELY = r"\bní\s+ṣísẹ̀\s+n\s+tẹ̀lé\b"
LIST_SEPARATOR = r"\s*(?:,\s*(?:àti\s+|tàbí\s+)?|àti\s+|tàbí\s+|&\s*)\s*"
ITEM_SEPARATOR = r"\s*,\s*-?\d[\d,]*(?:\.\d+)?\s*%?\s*;\s*(?:(?:àti|tàbí)\s+)?"
LIST_JOINERS = r"\b(?:àti|tàbí)\b|&"

UNCHECKED: tuple[str, ...] = (
    "pọ̀ síi",
    "dínkù",
    "lékè",
    "borí",
    "jọra",
    "fẹ́rẹ̀",
    "ọ̀pọ̀lọpọ̀",
    "pàtàkì",
    "gòkè",
    "sọ̀kalẹ̀",
)
UNCHECKED_PATTERNS: tuple[str, ...] = (r"\bbí\s+(?:\w+\s+){1,2}bí\b", r"\bó\s+kéré\s+tán\b")
SPELLED_NUMBERS: tuple[str, ...] = (
    "òdo",
    "ọ̀kan",
    "méjì",
    "mẹ́ta",
    "mẹ́rin",
    "márùn-ún",
    "mẹ́fà",
    "méje",
    "mẹ́jọ",
    "mẹ́sàn-án",
    "mẹ́wàá",
)
SPELLED_VALUES: dict[str, int] = {w: i for i, w in enumerate(SPELLED_NUMBERS)}
STRUCTURAL: tuple[str, ...] = (r"\bọ̀kan\s+fún\b", r"\bọ̀wọ́\s+\d+:")
COUNT_NOUNS: tuple[str, ...] = ("ọ̀pá", "àmì", "ìlà", "ọ̀wọ́", "ìfojúbù", "ìsọ̀rí", "nǹkan")
LABEL_STANDIN = "nǹkan"
TOTAL_BEFORE = r"\bàpapọ̀\s*(?::|=)?\s*$"
TOTAL_AFTER = r"^\s*(?:lápapọ̀|ní\s+àpapọ̀)\b"
SHARE_AFTER = r"^\s*%\s*nínú\s+àpapọ̀\b"
NEUTRAL_WORDS: tuple[str, ...] = (
    "àti",
    "ni",
    "ní",
    "jẹ́",
    "fún",
    "pẹ̀lú",
    "sí",
    "ọ̀kọ̀ọ̀kan",
    "kọ̀ọ̀kan",
    "ìfojúbù",
    "ààlà",
    "àwọn",
    "nǹkan",
    "gbogbo",
    "tirẹ̀",
)
RESERVED_PHRASES: tuple[str, ...] = ("bákan náà", "ọ̀kan nínú", "kò sí ìyàtọ̀", "yàtọ̀ sí")
NOT_SUPERLATIVE: tuple[str, ...] = ()
SCALES: dict[str, float] = {"ẹgbẹ̀rún": 1e3, "mílíọ̀nù": 1e6, "bílíọ̀nù": 1e9}

MESSAGES: dict[str, str] = dict(en.MESSAGES)
