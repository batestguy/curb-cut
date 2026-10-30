"""English: sentence templates and the claim checker's vocabulary.

One module per language holds everything language-specific that :mod:`describe` needs:
the sentence templates the alt-text is built from, the words the claim checker recognises,
and a glossary hook for category names. Numbers are always written as digits, in every
language, so the number check works the same way everywhere.

To add a language, copy this module, translate the strings and word lists (keep the keys),
and register it in ``_lang/__init__.py``.
"""

from __future__ import annotations

from collections.abc import Sequence

CODE = "en"

# Category and series names as written in this language. English keeps the names as given
# in the data, so the glossary is empty (identity); a translation fills it in.
GLOSSARY: dict[str, str] = {}

TEMPLATES: dict[str, str] = {
    "kind_bar": "Bar chart",
    "kind_dot": "Dot plot",
    # Introductions. {interval} is the interval label, quoted verbatim.
    "intro_bars": "{kind}: {title}. {n} bars, one per {label}.",
    "intro_bars_ci": "{kind}: {title}. {n} bars, one per {label}, each with its {interval}.",
    "intro_dots": "{kind}: {title}. {n} dots, one per {label}.",
    "intro_dots_ci": "{kind}: {title}. {n} dots, one per {label}, each with its {interval}.",
    "intro_series": "{kind}: {title}. {n} rows, one per {label}, with {k} series: {names}.",
    "intro_series_ci": (
        "{kind}: {title}. {n} rows, one per {label}, with {k} series: {names}, "
        "each estimate with its {interval}."
    ),
    "intro_series_one": "{kind}: {title}. 1 row, for {name}, with {k} series: {names}.",
    "one_bar": "{kind}: {title}. 1 bar, for {clause}.",
    "one_dot": "{kind}: {title}. 1 dot, for {clause}.",
    "series_value": "{series}: {clause}.",
    "series_all_equal": "{series}: all {n} {things} are {value}.",
    "series_highest_ci": "{series}: highest estimate {high}{high_difference}.",
    # One category (or a tie) and its figure.
    "clause": "{names}, {each}{value}",
    "each": "each ",
    "share": " ({share}% of the total)",
    "interval_inline": " ({interval} {lower} to {upper})",
    # Extremes without intervals. Counts keep the P1 wording (Largest / Smallest).
    "largest": "Largest: {clause}.",
    "smallest": "Smallest: {clause}.",
    "highest": "Highest: {clause}.",
    "lowest": "Lowest: {clause}.",
    "series_extremes": "{series}: highest {high}; lowest {low}.",
    # Extremes with intervals: hedged ("estimate"), summary first, then the comparison.
    "highest_ci": "Highest estimate: {clause}{difference}.",
    "lowest_ci": "Lowest estimate: {clause}{difference}.",
    "series_extremes_ci": "{series}: highest estimate {high}{high_difference}; "
    "lowest estimate {low}{low_difference}.",
    "difference": ", and the survey {can} show a difference from the {which} estimate, {clause}",
    "can": "can",
    "cannot": "cannot",
    "next": "next",
    "other": "other",
    "all_equal": "All {n} {things} are {value}.",
    "things_bars": "bars",
    "things_dots": "dots",
    "things_estimates": "estimates",
    # Detail, after the summary.
    "intervals": "Intervals ({interval}): {items}.",
    "series_intervals": "{series}, intervals ({interval}): {items}.",
    "interval_item": "{name} {lower} to {upper}",
    "total": "Total: {total}.",
    "source": "Source: {source}.",
}

# Statistical findings (findings.py). Kept apart from TEMPLATES so they do not change which
# names the alt-text checker reserves. The "finding_*" sentences must pass the claim
# checker; the "findings_*" lines are counts and method, checked by the audit instead.
FINDINGS: dict[str, str] = {
    "series_lowest_ci": "{series}: lowest estimate {low}{low_difference}.",
    "finding_item": "{name}, {value}",
    # A ranking neighbour with its rank, hedged like the alt-text's extremes ("estimate").
    "finding_rank_item": "{name}, the {rank} estimate ({value})",
    "rank_top": "highest",
    "rank_bottom": "lowest",
    "rank_high": "{ordinal}-highest",
    "rank_low": "{ordinal}-lowest",
    "finding_one": "{prefix}{items}, is {direction} than {other}.",
    "finding_many": "{prefix}{items}, are each {direction} than {other}.",
    "finding_gap": "{name}: {a}, {va}, is {direction} than {b}, {vb}.",
    "finding_prefix": "{series}: ",
    "higher": "higher",
    "lower": "lower",
    "finding_review": "Read with care: {name}'s estimate is flagged for review.",
    "finding_review_series": "Read with care: {name}'s {series} estimate is flagged for review.",
    "findings_count": "{checked} {comparisons} checked, {supported} supported.",
    "comparison": "comparison",
    "comparisons": "comparisons",
    "findings_method": (
        "A comparison is supported when the difference between two estimates is larger than "
        "their survey uncertainty allows, after allowing for every comparison checked "
        "(Benjamini-Hochberg, false discovery rate {q}%). These describe the estimates; "
        "they do not say why they differ."
    ),
    "findings_dropped": (
        "{dropped} more {comparisons} not tested, because {they} involve an estimate that "
        "is suppressed, too imprecise or has an interval of zero width."
    ),
    "findings_withheld": (
        "Not shown or compared ({count}): {names}; too few respondents or no data."
    ),
    "findings_none": "None of the comparisons is supported.",
}

AND = "and"


def join(names: Sequence[str]) -> str:
    """'A', 'A and B', 'A, B and C'."""
    names = list(names)
    if len(names) == 1:
        return names[0]
    return ", ".join(names[:-1]) + f" {AND} " + names[-1]


def items(parts: Sequence[str]) -> str:
    """'A, 1%', 'A, 1%; and B, 2%', 'A, 1%; B, 2%; and C, 3%'. Commas keep each name and its
    value together and semicolons keep the items apart, so a long list stays clear when read
    aloud; the claim checker reads such a list as one list of names (ITEM_SEPARATOR)."""
    parts = list(parts)
    if len(parts) == 1:
        return parts[0]
    return "; ".join(parts[:-1]) + f"; {AND} " + parts[-1]


def ordinal(n: int) -> str:
    """'second' for 2 (words up to tenth, as ORDINAL_WORDS), then '11th', '21st', '22nd'."""
    for word, value in ORDINAL_WORDS.items():
        if value == n:
            return word
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def label(category_label: str) -> str:
    """The category label as it reads mid-sentence ('one per disability type')."""
    return category_label.lower()


# --- Claim vocabulary -------------------------------------------------------------------
# Everything is matched case-insensitively on whole words. Comparative wording that is not
# listed here is warned about where the checker detects it (see UNCHECKED, the "-er than"
# and "the -est" forms, and the fallback for clauses naming two or more groups); wording it
# does not detect is not checked at all.

MAX_WORDS: tuple[str, ...] = ("largest", "highest")
MIN_WORDS: tuple[str, ...] = ("smallest", "lowest")
# Only counted after "the" (or as a label, "Most:"), since "most" alone is often not a claim.
MAX_WORDS_AFTER_THE: tuple[str, ...] = ("most",)
MIN_WORDS_AFTER_THE: tuple[str, ...] = ("fewest",)
# A superlative followed by one of these is hedged: "the highest estimate".
HEDGES: tuple[str, ...] = ("estimate", "estimates", "estimated")

UP_WORDS: tuple[str, ...] = ("higher", "more", "larger")
DOWN_WORDS: tuple[str, ...] = ("lower", "fewer", "smaller", "less")
THAN = "than"

RATIO_WORDS: dict[str, float] = {
    "twice": 2.0,
    "half": 0.5,
    "double": 2.0,
    "triple": 3.0,
    "quadruple": 4.0,
}
# "A trails B" means A is lower than B.
DOWN_VERBS: tuple[str, ...] = ("trails", "trail", "trailed", "lags", "lag", "lagged")
TIMES = "times"
NUMBER_WORDS: dict[str, float] = {
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
}

# Ranks: "ranked 3 of 37", "ranks 3rd", "3rd highest", "the second-highest", "number one",
# "#2". Group names are fixed: rank (the position, digits or a word), of (the count,
# optional), dir (an extreme word, optional).
ORDINAL_WORDS: dict[str, int] = {
    "first": 1,
    "second": 2,
    "third": 3,
    "fourth": 4,
    "fifth": 5,
    "sixth": 6,
    "seventh": 7,
    "eighth": 8,
    "ninth": 9,
    "tenth": 10,
}
RANK_NUMBER_WORDS: dict[str, int] = {"one": 1, **{k: int(v) for k, v in NUMBER_WORDS.items()}}
_EXTREME = r"largest|highest|most|smallest|lowest|fewest"
_ORDINAL = r"\d+(?:st|nd|rd|th)|" + "|".join(ORDINAL_WORDS)
_OF = r"(?:\s+(?:out\s+)?of\s+(?:the\s+)?(?P<of>\d+))?"
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
ASCENDING_WORDS: tuple[str, ...] = ("smallest", "lowest", "fewest")

# Negation before a claim word ("not higher", "isn't the highest", "far from the largest").
# A negated claim is not checked: it gives an "unchecked claim" warning.
NEGATORS: tuple[str, ...] = (
    r"\bnot\b",
    r"n't\b",
    "n" + chr(0x2019) + r"t\b",  # curly apostrophe
    r"\bnever\b",
    r"\bno\b",
    r"\bhardly\b",
    r"\bneither\b",
    r"\bnor\b",
    r"\bwithout\b",
    r"\bfar\s+from\b",
)
# Words that qualify a superlative ("one of the highest", "the joint highest"): the
# superlative is then not checked, and a warning says so.
QUALIFIERS: tuple[str, ...] = (
    r"\bamong\b",
    r"\bone\s+of\b",
    r"\bjoint\b",
    r"\btied\b",
    r"\brunner[\s-]up\b",
    r"\bnear\b",
    r"\bnearly\b",
    r"\balmost\b",
    r"\btop\b",
)

# Equality between two named groups.
EQUALITY_BINARY: tuple[str, ...] = (r"the same as", r"equal to", r"equals")
EQUALITY_PAIR: tuple[str, ...] = (r"(?:are|were) (?:the same|equal)",)

# "No difference" and its close variants. These always fail: a survey cannot show that two
# groups are equal, only that it cannot tell them apart.
NO_DIFFERENCE: tuple[str, ...] = (
    r"\bno\s+(?:\w+\s+){0,2}differences?\b",
    r"\bnot\s+(?:\w+\s+){0,2}different\b",
    r"\bno\s+different\b",
    r"\b(?:do|does|did)\s+not\s+differ\b",
    r"\b(?:don't|doesn't|didn't)\s+differ\b",
    r"\bindistinguishable\b",
)

# The wording the checker accepts and checks: "the survey can / cannot show a difference".
DIFFERENCE = (
    r"\b(?P<modal>can|cannot|can\s+not|can't|could|could\s+not|couldn't)"
    r"\s+show\s+(?:a|any)\s+difference\b"
)
CANNOT: tuple[str, ...] = ("cannot", "can not", "can't", "could not", "couldn't")
BETWEEN = "between"
FROM = "from"

# Where one part of a clause ends and the next begins, for working out which groups an
# extreme word refers to ("Kano has the highest rate, followed by Lagos").
BREAKS: tuple[str, ...] = (
    r",\s+and\b",
    r",\s+but\b",
    r",\s+while\b",
    r",\s+whereas\b",
    r"\bfrom\b",
    r"\bthan\b",
    r"\bfollowed\s+by\b",
    r"\bahead\s+of\b",
    r"\bcompared\s+(?:with|to)\b",
    r"\bversus\b",
    r"\bvs\b",
    r"\bbut\b",
    r"\bwhile\b",
    r"\bwhereas\b",
)
# Contrast markers: a claim after one ("Kano, rather than Lagos, has the highest rate") is
# not checked; a warning says so.
CONTRASTS: tuple[str, ...] = (
    r"\brather\s+than\b",
    r"\binstead\s+of\b",
    r"\bunlike\b",
    r"\bexcept\b",
)
# Before a ratio word these make it approximate ("more than twice", "nearly 3 times"): it is
# not checked, and a warning says so.
RATIO_QUALIFIERS: tuple[str, ...] = (
    r"\bmore\s+than",
    r"\bless\s+than",
    r"\bover",
    r"\bunder",
    r"\balmost",
    r"\bnearly",
    r"\babout",
    r"\baround",
    r"\broughly",
    r"\bapproximately",
    r"\bat\s+least",
    r"\bat\s+most",
    r"\bup\s+to",
)
# A name right after one of these is not part of the claim: "the highest, not Lagos".
EXCLUDERS: tuple[str, ...] = (r"\bnot", r"\bnor", r"\bexcept", r"\bunlike", r"\bbut\s+not")
# Breaks that also end a list of names after a ratio word ("twice as high as Lagos, but").
STRONG_BREAKS: tuple[str, ...] = (
    r",\s+and\b",
    r"\bbut\b",
    r"\bwhile\b",
    r"\bwhereas\b",
    r"\bfollowed\s+by\b",
)
# "and" also starts a new part when a new subject follows ("... and Ibadan has ...", "...
# and Ibadan the lowest") or when it joins two superlatives ("the highest ... and the
# lowest"). These verbs mark a new subject; plural verbs ("A and B are") do not.
AND_SPLIT_VERBS: tuple[str, ...] = ("is", "has", "was", "had", "shows", "records", "at")
# What may stand between a comparison's names and the next comparator when the next one
# reuses the subject: "Lagos is lower than Kano and higher than Abuja", "but it is higher".
CONNECTOR = (
    r"[\s,]*(?:(?:and|but|or|while|whereas|yet)\s+)?(?:also\s+)?(?:(?:it|they)\s+)?"
    r"(?:(?:is|are|was|were|has|have|had)\s+)?(?:also\s+)?(?:(?:a|an)\s+)?"
    r"(?:(?:much|far|slightly|still|even)\s+)?"
)
# A part that starts with a verb has no subject of its own: "... and is the highest",
# "... and has the lowest rate". Its subject is the clause's first names.
ELLIPSIS = r"\s*(?:also\s+)?(?:is|are|was|were|has|have|had)\b"
# A number belongs to the name just before it when only these separate them: "Lagos's rate
# is 8.0%", "Kano (12.0%)", "Lagos has a rate of 8.0%", "Kano: 12.0%".
LINK_AFTER_NAME = (
    r"(?:'s|\u2019s)?\s*(?:(?:rate|value|figure|share|estimate)\s+)?"
    r"(?:(?:is|was|of|at|has|had|with|=)\s+)?(?:(?:a|an|the)\s+)?"
    r"(?:(?:rate|value|figure|share|estimate)\s+)?(?:of\s+)?[:,(]?\s*"
)
# ... and to the name just after it in "2.0% in Ibadan".
IN_NAME = r"\s*%?\s*(?:in|for)\s+(?:the\s+)?"
# Two numbers joined like this next to one name are an interval: lower, then upper.
RANGE_JOIN = r"\s*%?\s*(?:to|\u2013|\u2014)\s*"
# Numbers in a "respectively" clause pair with the names in order.
RESPECTIVELY = r"\brespectively\b"
# Separators inside a list of names: "A, B and C", "A or B".
LIST_SEPARATOR = r"\s*(?:,\s*(?:and\s+|or\s+)?|and\s+|or\s+|&\s*)\s*"
# Between the items of a list of names with values: "A, 1.0%; B, 2.0%; and C, 3.0%" (the
# text after a name up to the next name). A semicolon here does not end the clause.
ITEM_SEPARATOR = r"\s*,\s*-?\d[\d,]*(?:\.\d+)?\s*%?\s*;\s*(?:(?:and|or)\s+)?"
LIST_JOINERS = r"\b(?:and|or)\b|&"

# Comparative or trend words the checker does not test. Each one gives a warning.
UNCHECKED: tuple[str, ...] = (
    "greater",
    "greatest",
    "exceed",
    "exceeds",
    "exceeded",
    "outnumber",
    "outnumbers",
    "outnumbered",
    "surpass",
    "surpasses",
    "surpassed",
    "outpace",
    "outpaces",
    "increase",
    "increases",
    "increased",
    "decrease",
    "decreases",
    "decreased",
    "rise",
    "rises",
    "rose",
    "risen",
    "fall",
    "falls",
    "fell",
    "drop",
    "drops",
    "dropped",
    "grew",
    "grow",
    "grows",
    "decline",
    "declines",
    "declined",
    "doubled",
    "tripled",
    "halved",
    "quadrupled",
    "significant",
    "significantly",
    "majority",
    "minority",
    "dominate",
    "dominates",
    "dominated",
    "lead",
    "leads",
    "leading",
    "top",
    "tops",
    "ahead",
    "behind",
    "above",
    "below",
    "compared",
    "versus",
    "vs",
    "least",
    "biggest",
    "most",
    "fewest",
    "rank",
    "ranks",
    "ranked",
    "beat",
    "beats",
    "outrank",
    "outranks",
    "outperform",
    "outperforms",
    "outperformed",
    "similar",
    "comparable",
    "close",
    "roughly",
    "nearly",
    "almost",
    "statistically",
    "unlike",
    "likely",
    "unlikely",
    "tied",
    "joint",
    "runner-up",
    "among",
    "equivalent",
    "matches",
    "mirrors",
    "rest",
    "remaining",
)
# Comparative phrases the checker does not test.
UNCHECKED_PATTERNS: tuple[str, ...] = (
    r"\bas\s+(?:\w+\s+){1,2}as\b",
    r"\bup\s+to\b",
    r"\bat\s+least\b",
    r"\bat\s+most\b",
    r"\bon\s+par\b",
    r"\bthe\s+same\b",
    r"\b[a-z]*-?fold\b",
    r"\b(?:so|as)\s+(?:is|are|does|do|has|have)\b",
    r"\blikewise\b",
    r"\btoo\b",
)
# Numbers written as words. Next to a named group they give a warning: write digits.
SPELLED_NUMBERS: tuple[str, ...] = (
    "zero",
    "one",
    "two",
    "three",
    "four",
    "five",
    "six",
    "seven",
    "eight",
    "nine",
    "ten",
    "eleven",
    "twelve",
    "thirteen",
    "fourteen",
    "fifteen",
    "sixteen",
    "seventeen",
    "eighteen",
    "nineteen",
    "twenty",
    "thirty",
    "forty",
    "fifty",
    "sixty",
    "seventy",
    "eighty",
    "ninety",
    "hundred",
)
# Spelled counts read before a counting noun or the category label: "the four states".
SPELLED_VALUES: dict[str, int] = {w: i for i, w in enumerate(SPELLED_NUMBERS[:21])} | {
    "thirty": 30,
    "forty": 40,
    "fifty": 50,
    "sixty": 60,
    "seventy": 70,
    "eighty": 80,
    "ninety": 90,
}
# The generator's own wording that contains spelled numbers or several names: not claims.
STRUCTURAL: tuple[str, ...] = (r"\bone\s+per\b", r"\d+\s+series:")
# A chart-wide count is only read after one of these nouns ("37 bars", "2 series") or the
# category label and its plural ("4 states").
COUNT_NOUNS: tuple[str, ...] = (
    "bars",
    "bar",
    "dots",
    "dot",
    "rows",
    "row",
    "series",
    "categories",
    "category",
    "groups",
    "group",
    "estimates",
    "items",
    "item",
)
# The category label is replaced by this word before checking, so its words are not read
# as claims ("one per highest qualification").
LABEL_STANDIN = "items"
# A total is only read after "Total:" / "a total of" or before "in total".
TOTAL_BEFORE = r"\btotal\s*(?::|of|is|was|=)?\s*$"
TOTAL_AFTER = r"^\s*(?:in\s+total|in\s+all|altogether)\b"
# "...% of the total" is a share.
SHARE_AFTER = r"^\s*%\s*of\s+(?:the\s+)?total\b"
# A clause made only of names, numbers and these words lists values; it states no relation.
NEUTRAL_WORDS: tuple[str, ...] = (
    "and",
    "has",
    "have",
    "had",
    "is",
    "are",
    "was",
    "were",
    "with",
    "at",
    "of",
    "the",
    "a",
    "an",
    "rate",
    "rates",
    "each",
    "to",
    "in",
    "for",
    "per",
    "estimate",
    "estimates",
    "value",
    "values",
    "respectively",
    "interval",
    "intervals",
    "people",
    "persons",
    "total",
    "items",
    "s",
)
# Names that may not be used for categories or series: they collide with template and
# vocabulary words, so the checker could not tell the name from the word.
RESERVED_PHRASES: tuple[str, ...] = (
    "the same",
    "the same as",
    "equal to",
    "far from",
    "one of",
    "up to",
    "close to",
    "followed by",
    "ahead of",
    "compared with",
    "compared to",
    "no difference",
    "runner-up",
)
# Words ending in "-est" that are not superlatives.
NOT_SUPERLATIVE: tuple[str, ...] = (
    "rest",
    "west",
    "test",
    "interest",
    "forest",
    "request",
    "guest",
    "harvest",
    "contest",
    "protest",
    "quest",
    "chest",
    "nest",
    "conquest",
    "inquest",
    "behest",
    "midwest",
    "northwest",
    "southwest",
    "honest",
    "modest",
    "manifest",
    "latest",
)

SCALES: dict[str, float] = {"thousand": 1e3, "million": 1e6, "billion": 1e9}

# Problem messages and suggested wording.
MESSAGES: dict[str, str] = {
    "not_in_data": "not in the data",
    "belongs_to": "belongs to {right}, not {wrong}",
    "no_category": "no category named in the clause",
    "not_extreme": "{name} is not the {word}: {actual} is ({value})",
    "tied": "{name} is tied for {word} with {others}",
    "superlative_unsupported": (
        "with intervals, the survey cannot show that {name} is the {word}: the gap to "
        "{runner} is within the uncertainty"
    ),
    "suggest_hedge": "{name} has the {word} estimate",
    "not_comparative": "{left} ({a}) is not {word} than {right} ({b})",
    "comparative_unsupported": (
        "the survey cannot show that {left} is {word} than {right}: the difference "
        "{diff} is not more than {threshold}"
    ),
    "suggest_cannot": "the survey cannot show a difference",
    "ratio_wrong": "{left} is {actual} times {right}, not {claimed} (5% tolerance)",
    "ratio_unsupported": (
        "the survey cannot show a difference between {left} and {right}, so a ratio "
        "claim is not supported"
    ),
    "rank_wrong": "{name} ranks {actual}, not {claimed}",
    "rank_count_wrong": "there are {actual} categories, not {claimed}",
    "rank_unsupported": (
        "the rank of {name} is not statistically supported: its interval test cannot "
        "separate it from {neighbour}"
    ),
    "equal_wrong": "{left} ({a}) is not the same as {right} ({b})",
    "equal_ci": "with intervals, a survey cannot show that two groups are the same",
    "no_difference": "'no difference' is not something a survey can show",
    "suggest_same": "{left} is the same as {right}",
    "can_wrong": "the survey cannot show a difference between {left} and {right}",
    "cannot_wrong": "the survey can show a difference between {left} and {right}",
    "independence": (
        "the interval test assumes independent groups; {why}, so the result may not hold"
    ),
    "why_series": "these are two series for the same category",
    "why_shares": "these are parts of one whole",
    "unchecked": "unchecked claim: '{word}' is not in the checker's vocabulary",
    "unchecked_than": "unchecked claim: comparison with something other than a named group",
    "unchecked_unresolved": "unchecked claim: could not tell which groups '{word}' compares",
    "unchecked_series": "unchecked claim: could not tell which series '{word}' refers to",
    "negated": "unchecked claim: negated comparison ('{negator} ... {word}') is not checked",
    "qualified": "unchecked claim: qualified superlative ('{qualifier} ... {word}') is not checked",
    "spelled": "unchecked number: '{word}' is written as a word; write numbers as digits",
    "relation": "unchecked relation between {names}: no recognised claim joins them",
    "count_wrong": "there are {actual} of them, not {claimed}",
    "interval_pair": "{name}'s interval is {lower} to {upper}, not {claimed}",
    "respectively_mismatch": (
        "unchecked claim: 'respectively' pairs {names} names with {numbers} numbers"
    ),
    "no_category_known": (
        "no category named in the clause (the number is in the data, but whose it is is not said)"
    ),
    "ratio_negative": "a ratio of values below zero is hard to read; check the wording",
    "reserved_name": (
        "{name!r} is also a word the alt-text templates or the claim checker use; rename it "
        "(for example {example!r}) so the checker can tell the name from the word"
    ),
}
