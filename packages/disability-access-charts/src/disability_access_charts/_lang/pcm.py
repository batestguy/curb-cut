"""Nigerian Pidgin (Naijá): sentence templates and the claim checker's vocabulary (new in 0.4).

**Drafted by an AI model (Claude), not reviewed by a native speaker.** Written in the
everyday spelling of BBC News Pidgin (English-based, no tone marks: "di", "dey", "wey",
"pass"). Same keys and placeholders as :mod:`disability_access_charts._lang.en`; numbers
stay as digits with "." as the decimal point. The word order is close to English, so most
of the vocabulary is English's; the differences: "di" as the article, comparisons with
"dey higher / lower pass" ("pass" for "than"), and "fit / no fit show difference" for "can /
cannot show a difference". ``MESSAGES`` and ``MAP_LEGEND`` stay English.
"""

from __future__ import annotations

from collections.abc import Sequence

from disability_access_charts._lang import en

CODE = "pcm"

FOLD = False
WORD = r"[a-z]+"
CAPITALS = r"\b[A-Z][a-z]+\b"
ARTICLE = r"di|the"
HEDGE_BEFORE = ""
UP_VERBS: tuple[str, ...] = ()
COUNT_BEFORE = False
SERIES_NOUNS: tuple[str, ...] = ("series",)
LEVEL = en.LEVEL
NOT_NAME = r"(?:\bbut\s+)?\bnot\s+(?:(?:di|the)\s+)?"
UNKNOWN_SUPERLATIVE = r"\b(?:di|the)\s+(?P<w>[a-z]+est)\b"

GLOSSARY: dict[str, str] = {}

TEMPLATES: dict[str, str] = {
    "kind_bar": "Bar chart",
    "kind_dot": "Dot plot",
    "intro_bars": "{kind}: {title}. {n} bars, one for each {label}.",
    "intro_bars_ci": (
        "{kind}: {title}. {n} bars, one for each {label}, and each of dem get im own {interval}."
    ),
    "intro_dots": "{kind}: {title}. {n} dots, one for each {label}.",
    "intro_dots_ci": (
        "{kind}: {title}. {n} dots, one for each {label}, and each of dem get im own {interval}."
    ),
    "intro_series": "{kind}: {title}. {n} rows, one for each {label}, wit {k} series: {names}.",
    "intro_series_ci": (
        "{kind}: {title}. {n} rows, one for each {label}, wit {k} series: {names}, "
        "and each estimate get im own {interval}."
    ),
    "intro_series_one": "{kind}: {title}. 1 row, for {name}, wit {k} series: {names}.",
    "one_bar": "{kind}: {title}. 1 bar, for {clause}.",
    "one_dot": "{kind}: {title}. 1 dot, for {clause}.",
    "series_value": "{series}: {clause}.",
    "series_all_equal": "{series}: all {n} {things} na {value}.",
    "series_highest_ci": "{series}: di highest estimate na {high}{high_difference}.",
    "clause": "{names}, {each}{value}",
    "each": "each ",
    "share": " ({share}% of di total)",
    "interval_inline": " ({interval} {lower} to {upper})",
    "largest": "Di biggest: {clause}.",
    "smallest": "Di smallest: {clause}.",
    "highest": "Di highest: {clause}.",
    "lowest": "Di lowest: {clause}.",
    "series_extremes": "{series}: di highest na {high}; di lowest na {low}.",
    "highest_ci": "Di highest estimate: {clause}{difference}.",
    "lowest_ci": "Di lowest estimate: {clause}{difference}.",
    "series_extremes_ci": "{series}: di highest estimate na {high}{high_difference}; "
    "di lowest estimate na {low}{low_difference}.",
    "difference": ", and di survey {can} show difference from di {which} estimate, {clause}",
    "can": "fit",
    "cannot": "no fit",
    "next": "next",
    "other": "oda",
    "all_equal": "All {n} {things} na {value}.",
    "things_bars": "bars",
    "things_dots": "dots",
    "things_estimates": "estimates",
    "intervals": "Intervals ({interval}): {items}.",
    "series_intervals": "{series}, intervals ({interval}): {items}.",
    "interval_item": "{name} {lower} to {upper}",
    "total": "Total: {total}.",
    "source": "Source: {source}.",
}

MAP_LEGEND: dict[str, str] = dict(en.MAP_LEGEND)

MAP_TEXT: dict[str, str] = {
    "kind_map": "Map",
    "intro_map": "{kind}: {title}. {n} {noun}.",
    "intro_map_ci": "{kind}: {title}. {n} {noun}, and each of dem get im own {interval}.",
    "classes": "Di colours dey for {k} groups: {items}.",
    "class_item": "{label}, {count} {noun}",
    "class_under": "Under {b}",
    "class_between": "{lo} to under {hi}",
    "class_over": "{b} and above",
}

FINDINGS: dict[str, str] = {
    "series_lowest_ci": "{series}: di lowest estimate na {low}{low_difference}.",
    "finding_item": "{name}, {value}",
    "finding_rank_item": "{name}, di {rank} estimate ({value})",
    "rank_top": "highest",
    "rank_bottom": "lowest",
    "rank_high": "{ordinal} highest",
    "rank_low": "{ordinal} lowest",
    "finding_one": "{prefix}{items}, dey {direction} pass {other}.",
    "finding_many": "{prefix}{items}, each of dem dey {direction} pass {other}.",
    "finding_gap": "{name}: {a}, {va}, dey {direction} pass {b}, {vb}.",
    "finding_prefix": "{series}: ",
    "higher": "higher",
    "lower": "lower",
    "finding_review": "Read am well: di estimate for {name} get flag for review.",
    "finding_review_series": "Read am well: di {series} estimate for {name} get flag for review.",
    "findings_count": "{checked} {comparisons} we check, {supported} get support.",
    "comparison": "comparison",
    "comparisons": "comparisons",
    "findings_method": (
        "We count one comparison as supported if di difference between two estimates big "
        "pass wetin di survey uncertainty allow, after we don count all di comparisons wey we "
        "check (Benjamini-Hochberg, false discovery rate {q}%). Dis ones dey describe di "
        "estimates; dem no talk why dem different."
    ),
    "findings_dropped": (
        "{dropped} more {comparisons} we no test, because {they} get estimate wey dem hide, "
        "wey no too correct, or wey im interval no get width."
    ),
    "findings_withheld": (
        "We no show or compare dem ({count}): {names}; di people wey answer no reach, or no "
        "data dey."
    ),
    "findings_none": "None of di comparisons get support.",
    "they_one": "e",
    "they_many": "dem",
}

AND = "and"


def join(names: Sequence[str]) -> str:
    """'A', 'A and B', 'A, B and C'."""
    names = list(names)
    if len(names) == 1:
        return names[0]
    return ", ".join(names[:-1]) + f" {AND} " + names[-1]


def items(parts: Sequence[str]) -> str:
    """'A, 1%; B, 2%; and C, 3%' (as en.items)."""
    parts = list(parts)
    if len(parts) == 1:
        return parts[0]
    return "; ".join(parts[:-1]) + f"; {AND} " + parts[-1]


def ordinal(n: int) -> str:
    """As English: 'second' up to 'tenth', then '11th'."""
    return en.ordinal(n)


def label(category_label: str) -> str:
    return category_label.lower()


def plural(noun: str, n: int) -> str:
    return en.plural(noun, n)


# --- Claim vocabulary: English's, with Pidgin's article, "pass" and "fit" ---------------

MAX_WORDS: tuple[str, ...] = ("largest", "highest", "biggest")
MIN_WORDS: tuple[str, ...] = ("smallest", "lowest")
MAX_WORDS_AFTER_THE: tuple[str, ...] = en.MAX_WORDS_AFTER_THE
MIN_WORDS_AFTER_THE: tuple[str, ...] = en.MIN_WORDS_AFTER_THE
HEDGES: tuple[str, ...] = en.HEDGES

UP_WORDS: tuple[str, ...] = ("higher", "more", "larger", "bigger")
DOWN_WORDS: tuple[str, ...] = ("lower", "fewer", "smaller", "less")
THAN = "pass"

RATIO_WORDS: dict[str, float] = dict(en.RATIO_WORDS)
DOWN_VERBS: tuple[str, ...] = en.DOWN_VERBS
TIMES = en.TIMES
NUMBER_WORDS: dict[str, float] = dict(en.NUMBER_WORDS)

ORDINAL_WORDS: dict[str, int] = dict(en.ORDINAL_WORDS)
RANK_NUMBER_WORDS: dict[str, int] = dict(en.RANK_NUMBER_WORDS)
_EXTREME = r"largest|highest|biggest|most|smallest|lowest|fewest"
_ORDINAL = r"\d+(?:st|nd|rd|th)|" + "|".join(ORDINAL_WORDS)
_OF = r"(?:\s+(?:out\s+)?of\s+(?:(?:di|the)\s+)?(?P<of>\d+))?"
_DIR = r"(?:[\s-]+(?P<dir>" + _EXTREME + r"))?"
RANK_PATTERNS: tuple[str, ...] = (
    r"\b(?:is\s+)?rank(?:ed|s)?\s+(?:at\s+)?(?:number\s+)?(?P<rank>\d+(?:st|nd|rd|th)?|"
    + "|".join(ORDINAL_WORDS)
    + r")\b"
    + _DIR
    + _OF,
    r"\b(?P<rank>" + _ORDINAL + r")\b" + _DIR + _OF,
    r"\bnumber\s+(?P<rank>\d+|" + "|".join(RANK_NUMBER_WORDS) + r")\b" + _DIR + _OF,
    r"#(?P<rank>\d+)\b" + _DIR + _OF,
)
ASCENDING_WORDS: tuple[str, ...] = en.ASCENDING_WORDS

NEGATORS: tuple[str, ...] = (*en.NEGATORS, r"\bneva\b")
QUALIFIERS: tuple[str, ...] = en.QUALIFIERS
EQUALITY_BINARY: tuple[str, ...] = (r"di same as", r"the same as", r"same as", r"equal to")
EQUALITY_PAIR: tuple[str, ...] = (r"(?:na|be|dey) (?:di same|the same|same|equal)",)
NO_DIFFERENCE: tuple[str, ...] = (
    r"\bno\s+difference\b",
    r"\bno\s+get\s+difference\b",
    r"\bno\s+(?:dey\s+)?different\b",
    r"\bnot\s+different\b",
    r"\bsame\s+same\b",
    r"\bindistinguishable\b",
)
DIFFERENCE = (
    r"\b(?P<modal>no\s+fit|fit|cannot|can\s+not|can't|can)"
    r"\s+show\s+(?:a\s+|any\s+)?difference\b"
)
CANNOT: tuple[str, ...] = ("no fit", "cannot", "can not", "can't")
BETWEEN = "between"
FROM = "from"

BREAKS: tuple[str, ...] = (*en.BREAKS, r"\bpass\b")
CONTRASTS: tuple[str, ...] = en.CONTRASTS
RATIO_QUALIFIERS: tuple[str, ...] = (*en.RATIO_QUALIFIERS, r"\bpass")
EXCLUDERS: tuple[str, ...] = en.EXCLUDERS
STRONG_BREAKS: tuple[str, ...] = en.STRONG_BREAKS
AND_SPLIT_VERBS: tuple[str, ...] = ()
CONNECTOR = (
    r"[\s,]*(?:(?:and|but|or|while|yet)\s+)?(?:also\s+)?(?:(?:e|dem|it|they)\s+)?"
    r"(?:(?:dey|is|are|na)\s+)?(?:also\s+)?(?:(?:much|far|small|still|even)\s+)?"
)
ELLIPSIS = r"\s*(?:also\s+)?(?:dey|is|are)\s+(?:higher|lower|more|less|bigger|smaller)\b"
LINK_AFTER_NAME = en.LINK_AFTER_NAME
IN_NAME = r"\s*%?\s*(?:in|for)\s+(?:(?:di|the)\s+)?"
RANGE_JOIN = en.RANGE_JOIN
RESPECTIVELY = en.RESPECTIVELY
LIST_SEPARATOR = en.LIST_SEPARATOR
ITEM_SEPARATOR = en.ITEM_SEPARATOR
LIST_JOINERS = en.LIST_JOINERS

UNCHECKED: tuple[str, ...] = tuple(w for w in en.UNCHECKED if w not in ("biggest",))
UNCHECKED_PATTERNS: tuple[str, ...] = en.UNCHECKED_PATTERNS
SPELLED_NUMBERS: tuple[str, ...] = en.SPELLED_NUMBERS
SPELLED_VALUES: dict[str, int] = dict(en.SPELLED_VALUES)
STRUCTURAL: tuple[str, ...] = (r"\bone\s+for\s+each\b", r"\d+\s+series:")
COUNT_NOUNS: tuple[str, ...] = en.COUNT_NOUNS
LABEL_STANDIN = en.LABEL_STANDIN
TOTAL_BEFORE = en.TOTAL_BEFORE
TOTAL_AFTER = en.TOTAL_AFTER
SHARE_AFTER = r"^\s*%\s*of\s+(?:(?:di|the)\s+)?total\b"
NEUTRAL_WORDS: tuple[str, ...] = (*en.NEUTRAL_WORDS, "di", "na", "dey", "get", "im", "own", "wit")
RESERVED_PHRASES: tuple[str, ...] = en.RESERVED_PHRASES
NOT_SUPERLATIVE: tuple[str, ...] = en.NOT_SUPERLATIVE
SCALES: dict[str, float] = dict(en.SCALES)

MESSAGES: dict[str, str] = dict(en.MESSAGES)
