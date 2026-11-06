"""Igbo: sentence templates and the claim checker's vocabulary (new in 0.4).

**Drafted by an AI model (Claude), not reviewed by a native speaker.** Standard Igbo
spelling with ị ọ ụ and ṅ; tone marks are left out, as in most printed Igbo. Same keys and
placeholders as :mod:`disability_access_charts._lang.en`; numbers stay as digits with "."
as the decimal point. ``FOLD = True``: the checker reads the text and this table without
the dots (``_lang.fold``). Differences from English that the checker is told about:

* a counting noun comes before its number ("Ntụpọ 37", ``COUNT_BEFORE``);
* the hedge comes before the superlative ("Atụmatụ kachasị elu", the estimate that is
  highest; ``HEDGE_BEFORE``);
* comparisons are the verbs "dị elu karịa" (is higher than) and "dị ala karịa" (is lower
  than);
* ranks use digits: "atụmatụ nke 2 site n'elu" (the estimate 2nd from the top).

Ratios ("okpukpu abụọ") are not recognised. ``MESSAGES`` and ``MAP_LEGEND`` stay English.
"""

from __future__ import annotations

from collections.abc import Sequence

from disability_access_charts._lang import en

CODE = "ig"

FOLD = True
WORD = r"[^\W\d_]+"
CAPITALS = r"\b[^\W\d_]+\b"
ARTICLE = r"(?!)"
HEDGE_BEFORE = r"\batụmatụ\s+"
UP_VERBS: tuple[str, ...] = ("dị elu karịa",)
COUNT_BEFORE = True
SERIES_NOUNS: tuple[str, ...] = ("usoro",)
LEVEL = r"\bobi\s+(\d+(?:\.\d+)?)\s*%"
NOT_NAME = r"(?!)"
UNKNOWN_SUPERLATIVE = ""

GLOSSARY: dict[str, str] = {}

TEMPLATES: dict[str, str] = {
    "kind_bar": "Eserese ogwe",
    "kind_dot": "Eserese ntụpọ",
    "intro_bars": "{kind}: {title}. Ogwe {n}, otu maka {label} ọ bụla.",
    "intro_bars_ci": (
        "{kind}: {title}. Ogwe {n}, otu maka {label} ọ bụla, nke ọ bụla nwere {interval} ya."
    ),
    "intro_dots": "{kind}: {title}. Ntụpọ {n}, otu maka {label} ọ bụla.",
    "intro_dots_ci": (
        "{kind}: {title}. Ntụpọ {n}, otu maka {label} ọ bụla, nke ọ bụla nwere {interval} ya."
    ),
    "intro_series": (
        "{kind}: {title}. Ahịrị {n}, otu maka {label} ọ bụla, nwere usoro {k}: {names}."
    ),
    "intro_series_ci": (
        "{kind}: {title}. Ahịrị {n}, otu maka {label} ọ bụla, nwere usoro {k}: {names}, "
        "atụmatụ ọ bụla nwere {interval} ya."
    ),
    "intro_series_one": "{kind}: {title}. Ahịrị 1, maka {name}, nwere usoro {k}: {names}.",
    "one_bar": "{kind}: {title}. Ogwe 1, maka {clause}.",
    "one_dot": "{kind}: {title}. Ntụpọ 1, maka {clause}.",
    "series_value": "{series}: {clause}.",
    "series_all_equal": "{series}: {things} {n} niile bụ {value}.",
    "series_highest_ci": "{series}: atụmatụ kachasị elu bụ {high}{high_difference}.",
    "clause": "{names}, {each}{value}",
    "each": "nke ọ bụla ",
    "share": " ({share}% nke ngụkọta)",
    "interval_inline": " ({interval} {lower} ruo {upper})",
    "largest": "Nke kachasị ukwuu: {clause}.",
    "smallest": "Nke kachasị nta: {clause}.",
    "highest": "Nke kachasị elu: {clause}.",
    "lowest": "Nke kachasị ala: {clause}.",
    "series_extremes": "{series}: nke kachasị elu bụ {high}; nke kachasị ala bụ {low}.",
    "highest_ci": "Atụmatụ kachasị elu: {clause}{difference}.",
    "lowest_ci": "Atụmatụ kachasị ala: {clause}{difference}.",
    "series_extremes_ci": "{series}: atụmatụ kachasị elu bụ {high}{high_difference}; "
    "atụmatụ kachasị ala bụ {low}{low_difference}.",
    "difference": ", ma nnyocha ahụ {can} igosi ọdịiche ya na {which}, {clause}",
    "can": "nwere ike",
    "cannot": "enweghị ike",
    "next": "atụmatụ na-esote",
    "other": "atụmatụ nke ọzọ",
    "all_equal": "Ha niile, {things} {n}, bụ {value}.",
    "things_bars": "ogwe",
    "things_dots": "ntụpọ",
    "things_estimates": "atụmatụ",
    "intervals": "Oke ({interval}): {items}.",
    "series_intervals": "{series}, oke ({interval}): {items}.",
    "interval_item": "{name} {lower} ruo {upper}",
    "total": "Ngụkọta: {total}.",
    "source": "Isi mmalite: {source}.",
}

MAP_LEGEND: dict[str, str] = dict(en.MAP_LEGEND)

MAP_TEXT: dict[str, str] = {
    "kind_map": "Maapụ",
    "intro_map": "{kind}: {title}. O nwere {noun} {n}.",
    "intro_map_ci": "{kind}: {title}. O nwere {noun} {n}, nke ọ bụla nwere {interval} ya.",
    "classes": "E kewara ha n'ụdị agba {k}: {items}.",
    "class_item": "{label}, {noun} {count}",
    "class_under": "Erughị {b}",
    "class_between": "site na {lo} ruo n'okpuru {hi}",
    "class_over": "{b} gaa n'elu",
}

FINDINGS: dict[str, str] = {
    "series_lowest_ci": "{series}: atụmatụ kachasị ala bụ {low}{low_difference}.",
    "finding_item": "{name}, {value}",
    "finding_rank_item": "{name}, {rank} ({value})",
    "rank_top": "atụmatụ kachasị elu",
    "rank_bottom": "atụmatụ kachasị ala",
    "rank_high": "atụmatụ nke {ordinal} site n'elu",
    "rank_low": "atụmatụ nke {ordinal} site n'ala",
    "finding_one": "{prefix}{items}, {direction} {other}.",
    "finding_many": "{prefix}{items}, nke ọ bụla n'ime ha {direction} {other}.",
    "finding_gap": "{name}: {a}, {va}, {direction} {b}, {vb}.",
    "finding_prefix": "{series}: ",
    "higher": "dị elu karịa",
    "lower": "dị ala karịa",
    "finding_review": "Gụọ ya nke ọma: e debere akara n'atụmatụ {name} ka e nyochaa ya ọzọ.",
    "finding_review_series": (
        "Gụọ ya nke ọma: e debere akara n'atụmatụ {series} maka {name} ka e nyochaa ya ọzọ."
    ),
    "findings_count": "E nyochara {comparisons} {checked}; {supported} nwere ihe akaebe.",
    "comparison": "ntụnyere",
    "comparisons": "ntụnyere",
    "findings_method": (
        "A na-ewere ntụnyere dị ka nke nwere ihe akaebe mgbe ọdịiche dị n'etiti atụmatụ abụọ "
        "karịrị ihe ejighị n'aka nke nnyocha ahụ kwere, mgbe e lebachara anya na ntụnyere "
        "niile e nyochara (Benjamini-Hochberg, ọnụego nchọpụta ụgha {q}%). Ndị a na-akọwa "
        "atụmatụ ndị ahụ; ha anaghị ekwu ihe kpatara ọdịiche ha."
    ),
    "findings_dropped": (
        "E nyochaghị {comparisons} {dropped} ọzọ, n'ihi na {they} gụnyere atụmatụ e zoro ezo, "
        "nke na-ezighị ezi nke ọma, ma ọ bụ nke oke ya enweghị obosara."
    ),
    "findings_withheld": (
        "E gosighị ha, e tụnyereghị ha ({count}): {names}; ndị zara ajụjụ adịghị ọtụtụ ma ọ "
        "bụ enweghị data."
    ),
    "findings_none": "Ọ dịghị otu n'ime ntụnyere ndị ahụ nwere ihe akaebe.",
    "they_one": "ọ",
    "they_many": "ha",
}

AND = "na"


def join(names: Sequence[str]) -> str:
    """'A', 'A na B', 'A, B na C'."""
    names = list(names)
    if len(names) == 1:
        return names[0]
    return ", ".join(names[:-1]) + f" {AND} " + names[-1]


def items(parts: Sequence[str]) -> str:
    """'A, 1%; B, 2%; na C, 3%' (as en.items)."""
    parts = list(parts)
    if len(parts) == 1:
        return parts[0]
    return "; ".join(parts[:-1]) + f"; {AND} " + parts[-1]


def ordinal(n: int) -> str:
    """Ranks are written with digits: 'nke 2'."""
    return str(n)


def label(category_label: str) -> str:
    return category_label.lower()


def plural(noun: str, n: int) -> str:
    """Igbo nouns do not change for the plural ('steeti 37')."""
    del n
    return noun


# --- Claim vocabulary (see en.py for what each list does) -------------------------------

MAX_WORDS: tuple[str, ...] = ("kachasị elu", "kachasị ukwuu")
MIN_WORDS: tuple[str, ...] = ("kachasị ala", "kachasị nta")
MAX_WORDS_AFTER_THE: tuple[str, ...] = ()
MIN_WORDS_AFTER_THE: tuple[str, ...] = ()
HEDGES: tuple[str, ...] = ("atụmatụ",)

UP_WORDS: tuple[str, ...] = ()
DOWN_WORDS: tuple[str, ...] = ()
THAN = "karịa"

RATIO_WORDS: dict[str, float] = {"okpukpu abụọ": 2.0, "ọkara": 0.5, "okpukpu atọ": 3.0}
DOWN_VERBS: tuple[str, ...] = ("dị ala karịa",)
TIMES = "okpukpu"
NUMBER_WORDS: dict[str, float] = {
    "abụọ": 2,
    "atọ": 3,
    "anọ": 4,
    "ise": 5,
    "isii": 6,
    "asaa": 7,
    "asatọ": 8,
    "itoolu": 9,
    "iri": 10,
}

ORDINAL_WORDS: dict[str, int] = {}
RANK_NUMBER_WORDS: dict[str, int] = {"otu": 1, **{k: int(v) for k, v in NUMBER_WORDS.items()}}
RANK_PATTERNS: tuple[str, ...] = (
    r"\bnke\s+(?P<rank>\d+)(?:\s+n['’]ime\s+(?P<of>\d+))?\s+site\s+n['’](?P<dir>elu|ala)\b",
)
ASCENDING_WORDS: tuple[str, ...] = ("ala",)

NEGATORS: tuple[str, ...] = (
    r"\benweghị\b",
    r"\babụghị\b",
    r"\bọ\s+bụghị\b",
    r"\bọ\s+dịghị\b",
    r"\badịghị\b",
)
QUALIFIERS: tuple[str, ...] = (
    r"\botu\s+n['’]ime\b",
    r"\bihe\s+dị\s+ka\b",
    r"\bọ\s+fọrọ\s+obere\b",
)
EQUALITY_BINARY: tuple[str, ...] = (r"nhata\s+na",)
EQUALITY_PAIR: tuple[str, ...] = (r"(?:hà\s+)?nhata",)
NO_DIFFERENCE: tuple[str, ...] = (
    r"\benweghị\s+ọdịiche\b",
    r"\bọ\s+dịghị\s+ọdịiche\b",
    r"\bọdịiche\s+ọ\s+bụla\s+adịghị\b",
)
DIFFERENCE = r"\b(?P<modal>nwere\s+ike|enweghị\s+ike)\s+igosi\s+ọdịiche(?:\s+ya)?"
CANNOT: tuple[str, ...] = ("enweghị ike",)
BETWEEN = "n'etiti"
FROM = "na"

BREAKS: tuple[str, ...] = (
    r",\s+ma\b",
    r",\s+mana\b",
    r"\bmana\b",
    r"\bdị\s+elu\s+karịa\b",
    r"\bdị\s+ala\s+karịa\b",
    r"\bkarịa\b",
)
CONTRASTS: tuple[str, ...] = (r"\bkama\b", r"\bewezuga\b")
RATIO_QUALIFIERS: tuple[str, ...] = (r"\bkarịa", r"\bihe\s+dị\s+ka", r"\bopekata\s+mpe")
EXCLUDERS: tuple[str, ...] = (r"\bewezuga", r"\bọ\s+bụghị")
STRONG_BREAKS: tuple[str, ...] = (r",\s+ma\b", r"\bmana\b")
AND_SPLIT_VERBS: tuple[str, ...] = ()
CONNECTOR = r"[\s,]*(?:(?:ma|mana|na)\s+)?(?:ọ\s+)?"
ELLIPSIS = r"\s*(?:ọ\s+)?dị\s+(?:elu|ala)\s+karịa\b"
LINK_AFTER_NAME = r"\s*[:,(]?\s*"
IN_NAME = r"\s*%?\s*n['’]\s*"
RANGE_JOIN = r"\s*%?\s*(?:ruo|–|—)\s*"
RESPECTIVELY = r"\bn['’]usoro\s+ha\b"
LIST_SEPARATOR = r"\s*(?:,\s*(?:na\s+|ma\s+ọ\s+bụ\s+)?|na\s+|ma\s+ọ\s+bụ\s+|&\s*)\s*"
ITEM_SEPARATOR = r"\s*,\s*-?\d[\d,]*(?:\.\d+)?\s*%?\s*;\s*(?:(?:na|ma\s+ọ\s+bụ)\s+)?"
LIST_JOINERS = r"\b(?:na|ma\s+ọ\s+bụ)\b|&"

UNCHECKED: tuple[str, ...] = (
    "mụbara",
    "belatara",
    "rịrị elu",
    "yiri",
    "ọtụtụ",
    "karịrị",
    "gafere",
    "dịka",
    "dị mkpa",
)
UNCHECKED_PATTERNS: tuple[str, ...] = (r"\bopekata\s+mpe\b", r"\bihe\s+dị\s+ka\b")
SPELLED_NUMBERS: tuple[str, ...] = (
    "efu",
    "otu",
    "abụọ",
    "atọ",
    "anọ",
    "ise",
    "isii",
    "asaa",
    "asatọ",
    "itoolu",
    "iri",
)
SPELLED_VALUES: dict[str, int] = {w: i for i, w in enumerate(SPELLED_NUMBERS)}
STRUCTURAL: tuple[str, ...] = (r"\botu\s+maka\b", r"\busoro\s+\d+:")
COUNT_NOUNS: tuple[str, ...] = ("ogwe", "ntụpọ", "ahịrị", "usoro", "atụmatụ", "ụdị", "ihe")
LABEL_STANDIN = "ihe"
TOTAL_BEFORE = r"\bngụkọta\s*(?::|=)?\s*$"
TOTAL_AFTER = r"^\s*(?:na\s+ngụkọta)\b"
SHARE_AFTER = r"^\s*%\s*nke\s+ngụkọta\b"
NEUTRAL_WORDS: tuple[str, ...] = (
    "na",
    "nke",
    "bụ",
    "maka",
    "ọ",
    "bụla",
    "niile",
    "ha",
    "ruo",
    "atụmatụ",
    "oke",
    "ihe",
    "nwere",
    "ya",
)
RESERVED_PHRASES: tuple[str, ...] = ("otu n'ime", "enweghị ọdịiche", "ewezuga", "nhata na")
NOT_SUPERLATIVE: tuple[str, ...] = ()
SCALES: dict[str, float] = {"puku": 1e3, "nde": 1e6, "ijeri": 1e9}

MESSAGES: dict[str, str] = dict(en.MESSAGES)
