"""Hausa, Yoruba, Igbo and Pidgin (0.4): the tables, their claim checkers and translations."""

import copy
import dataclasses
import re
import string
from types import FunctionType
from typing import Any

import pytest
from disability_access_charts import (
    ChartData,
    Reference,
    Series,
    Translation,
    audit,
    check_alt_text,
    choropleth,
    describe,
    dot,
    grouped_bar,
)
from disability_access_charts import bar as bar_chart
from disability_access_charts._lang import LANGUAGES, checker, en, fold
from disability_access_charts.describe import check_reserved, errors

OTHERS = ("ha", "yo", "ig", "pcm")
STATE = {"en": "State", "ha": "Jiha", "yo": "Ìpínlẹ̀", "ig": "Steeti", "pcm": "State"}
INTERVAL = {
    "en": "95% confidence interval",
    "ha": "tazarar tabbaci ta 95%",
    "yo": "ààlà ìgbẹ́kẹ̀lé 95%",
    "ig": "oke ntụkwasị obi 95%",
    "pcm": "95% confidence interval",
}
NATION = {
    "ha": "Najeriya baki ɗaya",
    "yo": "Nàìjíríà lápapọ̀",
    "ig": "Naịjirịa niile",
    "pcm": "Naija as a whole",
}
TYPES = {
    "Physical": {"ha": "Jiki", "yo": "Ara", "ig": "Anụ ahụ", "pcm": "Body"},
    "Hearing": {"ha": "Jin sauti", "yo": "Gbígbọ́", "ig": "Ịnụ olu", "pcm": "To hear"},
    "Visual": {"ha": "Gani", "yo": "Ríran", "ig": "Ịhụ ụzọ", "pcm": "To see"},
}


def placeholders(template: str) -> set[str]:
    return {f for _, f, _, _ in string.Formatter().parse(template) if f}


def public(module: Any) -> set[str]:
    return {
        n
        for n, v in vars(module).items()
        if not n.startswith("_")
        and (n.isupper() or (isinstance(v, FunctionType) and v.__module__ == module.__name__))
    }


# --- The tables ---------------------------------------------------------------------------


@pytest.mark.parametrize("code", OTHERS)
def test_every_table_has_exactly_the_english_keys_and_placeholders(code: str) -> None:
    table = LANGUAGES[code]
    assert public(table) - {"CODE"} == public(en) - {"CODE"}
    assert code == table.CODE
    for name in ("TEMPLATES", "FINDINGS", "MAP_TEXT", "MAP_LEGEND", "MESSAGES"):
        theirs, ours = getattr(table, name), getattr(en, name)
        assert theirs.keys() == ours.keys(), name
        for key in ours:
            assert placeholders(theirs[key]) == placeholders(ours[key]), (name, key)


@pytest.mark.parametrize("code", ["en", *OTHERS])
def test_every_regex_compiles_raw_and_folded(code: str) -> None:
    for table in (LANGUAGES[code], checker(code)):
        for name in dir(table):
            value = getattr(table, name)
            patterns = value if isinstance(value, tuple) else (value,)
            if name.isupper() and all(isinstance(p, str) for p in patterns):
                for p in patterns:
                    re.compile(p)


def test_fold_removes_marks_and_keeps_hooked_letters() -> None:
    assert fold("Ẹ̀kọ́ ṣé ọmọ") == "Eko se omo"
    assert fold("ɓ ɗ ƙ ƴ ʼ") == "ɓ ɗ ƙ ƴ ʼ"
    assert fold("ị ụ ṅ") == "i u n"


def test_orthography_uses_the_language_letters() -> None:
    assert "ƙ" in LANGUAGES["ha"].TEMPLATES["lowest_ci"]
    assert "ɗ" in LANGUAGES["ha"].TEMPLATES["kind_dot"]
    assert (
        "ọ̀" in LANGUAGES["yo"].TEMPLATES["intro_bars"]
        and "jùlọ" in LANGUAGES["yo"].TEMPLATES["highest_ci"]
    )
    assert (
        "ị" in LANGUAGES["ig"].TEMPLATES["highest_ci"]
        and "ụ" in LANGUAGES["ig"].TEMPLATES["kind_dot"]
    )


def test_the_37_states_are_valid_names_in_every_language() -> None:
    states = [
        "Abia",
        "Adamawa",
        "Akwa-Ibom",
        "Anambra",
        "Bauchi",
        "Bayelsa",
        "Benue",
        "Borno",
        "Cross-River",
        "Delta",
        "Ebonyi",
        "Edo",
        "Ekiti",
        "Enugu",
        "Gombe",
        "Imo",
        "Jigawa",
        "Kaduna",
        "Kano",
        "Katsina",
        "Kebbi",
        "Kogi",
        "Kwara",
        "Lagos",
        "Nasarawa",
        "Niger",
        "Ogun",
        "Ondo",
        "Osun",
        "Oyo",
        "Plateau",
        "Rivers",
        "Sokoto",
        "Taraba",
        "Yobe",
        "Zamfara",
    ]
    names = [s.replace("-", " ") for s in states] + ["Federal Capital Territory"]
    ChartData(categories=tuple(names), series=(Series("Rate", tuple(range(len(names)))),))


# --- Generated text passes each language's checker ---------------------------------------


def localise(data: ChartData, code: str, names: dict[str, str] | None = None) -> ChartData:
    return dataclasses.replace(
        data,
        category_label=STATE[code],
        interval_label=INTERVAL[code],
        glossary=names or {},
    )


STATES4 = ("Kano", "Lagos", "Oyo", "Ekiti")
CI = ChartData(
    categories=STATES4,
    series=(Series("Rate", (12.3, 11.9, 6.0, 4.1), (10.1, 9.8, 4.9, 3.0), (14.5, 14.0, 7.1, 5.2)),),
    unit="percent",
    decimals=1,
    verbatim=("T", "S"),
)
POINT = dataclasses.replace(CI, series=(Series("Rate", (12.3, 11.9, 6.0, 4.1)),))
TWO = ChartData(
    categories=("Kano", "Lagos", "Oyo"),
    series=(
        Series("Women", (12.3, 11.9, 6.0), (10.1, 9.8, 4.9), (14.5, 14.0, 7.1)),
        Series("Men", (10.0, 9.0, 5.0), (8.0, 7.0, 4.0), (12.0, 11.0, 6.0)),
    ),
    unit="percent",
    decimals=1,
    verbatim=("T", "S"),
)
SERIES_NAMES = {
    "ha": {"Women": "Mata", "Men": "Maza"},
    "yo": {"Women": "Obìnrin", "Men": "Ọkùnrin"},
    "ig": {"Women": "Ụmụnwanyị", "Men": "Ụmụnwoke"},
    "pcm": {"Women": "Women", "Men": "Men"},
}
COUNTS = ChartData(
    categories=tuple(TYPES),
    series=(Series("Persons", (8186521, 7653482, 61511)),),
    unit="count",
    shares=True,
    verbatim=("T", "S"),
)


@pytest.mark.parametrize("code", OTHERS)
@pytest.mark.parametrize("chart_type", ["bar", "dot"])
@pytest.mark.parametrize(
    "case", ["intervals", "points", "two-series", "two-series-points", "counts"]
)
def test_generated_text_passes_its_own_checker(code: str, chart_type: str, case: str) -> None:
    if case == "intervals":
        data = localise(CI, code)
    elif case == "points":
        data = localise(POINT, code)
    elif case == "two-series":
        data = localise(TWO, code, SERIES_NAMES[code])
    elif case == "two-series-points":
        flat = dataclasses.replace(TWO, series=tuple(Series(s.name, s.values) for s in TWO.series))
        data = localise(flat, code, SERIES_NAMES[code])
    else:
        data = localise(COUNTS, code, {k: v[code] for k, v in TYPES.items()})
    text = describe(data, chart_type=chart_type, title="T", source="S", lang=code)
    assert check_alt_text(text, data, lang=code) == [], text


@pytest.mark.parametrize("code", OTHERS)
@pytest.mark.parametrize(
    "values",
    [
        (5.0,),
        (5.0, 5.0, 5.0),
        (5.0, 3.0),
        (5.0, 5.0, 1.0),
        (9.0, 1.0, 1.0),
        (9.0, 8.0, 7.0, 7.0, 1.0),
    ],
)
@pytest.mark.parametrize("interval", [False, True], ids=["points", "intervals"])
def test_edge_cases_pass_in_every_language(
    code: str, values: tuple[float, ...], interval: bool
) -> None:
    cats = tuple(["Kano", "Lagos", "Oyo", "Ekiti", "Edo"][: len(values)])
    series = Series(
        "Rate",
        values,
        tuple(v - 0.5 for v in values) if interval else None,
        tuple(v + 0.7 for v in values) if interval else None,
    )
    data = localise(ChartData(categories=cats, series=(series,), unit="percent", decimals=1), code)
    for chart_type in ("bar", "dot"):
        text = describe(data, chart_type=chart_type, title="T", source="S", lang=code)
        assert check_alt_text(text, data, lang=code) == [], text


@pytest.mark.parametrize("code", OTHERS)
def test_tampered_translations_are_caught(code: str) -> None:
    data = localise(CI, code)
    text = describe(data, title="T", source="S", lang=code)
    t = LANGUAGES[code].TEMPLATES
    # "can" and "cannot" swapped: Kano and Lagos overlap, so "can show a difference" is wrong.
    can, cannot = t["can"], t["cannot"]
    swapped = text.replace(cannot, "\0").replace(can, cannot).replace("\0", can)
    assert errors(check_alt_text(swapped, data, lang=code)), swapped
    # A wrong number.
    assert errors(check_alt_text(text.replace("12.3%", "13.3%"), data, lang=code))
    # A wrong interval bound.
    assert errors(check_alt_text(text.replace("10.1%", "10.6%"), data, lang=code))


# --- Documents ---------------------------------------------------------------------------

# Well separated, so rankings and outliers are supported; Ondo is flagged for review.
STATES5 = ("Kano", "Lagos", "Oyo", "Ondo", "Ekiti")
FIVE = Series(
    "Adults (%)",
    (20.0, 15.0, 10.0, 5.0, 2.0),
    (19.5, 14.5, 9.5, 4.5, 1.7),
    (20.5, 15.5, 10.5, 5.5, 2.3),
    ("reliable", "reliable", "reliable", "review", "reliable"),
)
NATIONAL = Reference("Nigeria as a whole", 8.0, 7.8, 8.2)


def translation(
    code: str, *, title: str = "Taken", names: dict | None = None, nation: bool = False
) -> Translation:
    return Translation(
        title=f"{title} 18+ ({code})",
        source="Nigeria DHS 2024 (NPC, ICF)",
        category_label=STATE[code],
        interval_label=INTERVAL[code],
        names={**({"Nigeria as a whole": NATION[code]} if nation else {}), **(names or {})},
    )


def dot_doc() -> dict:
    return dot(
        list(STATES5),
        [FIVE],
        title="Adults 18+",
        value_label="Adults (%)",
        category_label="State",
        source="Nigeria DHS 2024 (NPC, ICF)",
        findings=True,
        reference=NATIONAL,
        withheld=["Bauchi"],
        translations={c: translation(c, nation=True) for c in OTHERS},
    )


def assert_clean(doc: dict) -> None:
    result = doc["audit"]
    failed = [c for c in result["checks"] if not c["passed"]]
    assert result["passed"], failed
    assert result["warnings"] == 0, failed


def test_dot_plot_with_findings_carries_audited_translations() -> None:
    doc = dot_doc()
    assert_clean(doc)
    block = doc["alt_text_translations"]
    assert list(block) == list(OTHERS)
    for code in OTHERS:
        entry = block[code]
        assert entry["origin"] == "template" and entry["reviewed"] is False
        assert len(entry["findings"]) == len(doc["findings"]["statements"])
        ids = {c["id"] for c in doc["audit"]["checks"] if c.get("lang") == code}
        assert ids == {
            "alt-text-translation-valid",
            "alt-text-translation-matches-data",
            "alt-text-translation-unchecked-claims",
            "alt-text-translation-matches-template",
        }
    # The findings exercise comparisons, ranks, outliers both ways and the review hedge.
    families = {s["family"] for s in doc["findings"]["statements"]}
    assert {"extremes", "rankings", "outliers"} <= families
    assert any(s["hedged"] for s in doc["findings"]["statements"])


def test_grouped_bars_and_bars_carry_audited_translations() -> None:
    doc = grouped_bar(
        list(TWO.categories),
        list(TWO.series),
        title="Rate by sex",
        value_label="Rate (%)",
        category_label="State",
        source="S",
        findings=True,
        translations={c: translation(c, names=SERIES_NAMES[c]) for c in OTHERS},
    )
    assert_clean(doc)
    counts = bar_chart(
        list(TYPES),
        [8186521, 7653482, 61511],
        title="Persons by type",
        value_label="Persons",
        category_label="Type",
        source="JONAPWD",
        translations={
            c: Translation(
                "Persons by type",
                "JONAPWD",
                {"ha": "Iri", "yo": "Irú", "ig": "Ụdị", "pcm": "Type"}[c],
                names={k: v[c] for k, v in TYPES.items()},
            )
            for c in OTHERS
        },
    )
    assert_clean(counts)


def map_doc(**kw: Any) -> dict:
    names = list(STATES5)
    codes = [f"NG-{n[:2].upper()}" for n in names]
    paths = {c: f"M{i} 0h1v1h-1z" for i, c in enumerate(codes)}
    return choropleth(
        names,
        codes,
        list(FIVE.values),
        lower=list(FIVE.lower or ()),
        upper=list(FIVE.upper or ()),
        paths=paths,
        view_box="0 0 10 1",
        breaks=[3, 6, 12, 18],
        title="Adults 18+ by state",
        value_label="Adults (%)",
        source="Nigeria DHS 2024",
        translations={c: translation(c, title="Map") for c in OTHERS},
        **kw,
    )


def test_map_carries_audited_translations_with_their_class_sentence() -> None:
    doc = map_doc()
    assert_clean(doc)
    for code in OTHERS:
        entry = doc["alt_text_translations"][code]
        assert entry["classes"] in entry["text"]
        assert "findings" not in entry
    assert "ƙasa da 3%, jiha 1" in doc["alt_text_translations"]["ha"]["classes"]


@pytest.mark.parametrize("code", OTHERS)
@pytest.mark.parametrize("make", [dot_doc, map_doc], ids=["dot", "map"])
def test_a_wrong_number_in_a_translation_fails_the_claim_check(code: str, make) -> None:
    doc = make()
    bad = copy.deepcopy(doc)
    entry = bad["alt_text_translations"][code]
    assert "20.0%" in entry["text"]
    entry["text"] = entry["text"].replace("20.0%", "21.0%", 1)
    entry["origin"] = "human"  # so only the claim check and the number check can catch it
    result = audit(bad)
    assert not result["passed"]
    check = next(
        c
        for c in result["checks"]
        if c["id"] == "alt-text-translation-matches-data" and c["lang"] == code
    )
    assert not check["passed"]
    assert check["claim_problems"], check  # the language's claim checker caught it


@pytest.mark.parametrize("code", OTHERS)
def test_edited_wording_with_the_same_numbers_passes_as_human_but_not_as_template(
    code: str,
) -> None:
    doc = dot_doc()
    edited = copy.deepcopy(doc)
    edited["alt_text_translations"][code]["text"] += " "  # a harmless edit
    result = audit(edited)
    template = next(
        c
        for c in result["checks"]
        if c["id"] == "alt-text-translation-matches-template" and c["lang"] == code
    )
    assert not template["passed"]
    edited["alt_text_translations"][code]["origin"] = "human"
    assert audit(edited)["passed"]


@pytest.mark.parametrize("code", OTHERS)
def test_a_finding_without_its_hedge_fails(code: str) -> None:
    doc = dot_doc()
    bad = copy.deepcopy(doc)
    hedge = LANGUAGES[code].FINDINGS["finding_review"].format(name="Ondo")
    sentences = bad["alt_text_translations"][code]["findings"]
    hit = [i for i, s in enumerate(sentences) if hedge in s]
    assert hit
    sentences[hit[0]] = sentences[hit[0]].replace(hedge, "").strip()
    bad["alt_text_translations"][code]["origin"] = "human"
    check = next(
        c
        for c in audit(bad)["checks"]
        if c["id"] == "alt-text-translation-matches-data" and c["lang"] == code
    )
    assert not check["passed"]


def test_inputs_are_checked() -> None:
    with pytest.raises(ValueError, match="same level"):
        dot(
            list(STATES5),
            [FIVE],
            title="T",
            value_label="v",
            category_label="State",
            source="S",
            translations={"ha": dataclasses.replace(translation("ha"), interval_label="ta 90%")},
        )
    with pytest.raises(ValueError, match="not in the data"):
        dot(
            list(STATES5),
            [FIVE],
            title="T",
            value_label="v",
            category_label="State",
            source="S",
            translations={"ha": Translation("T", "S", "Jiha", INTERVAL["ha"], {"Abuja": "x"})},
        )
    with pytest.raises(ValueError, match="interval_label"):
        dot(
            list(STATES5),
            [FIVE],
            title="T",
            value_label="v",
            category_label="State",
            source="S",
            translations={"yo": Translation("T", "S", "Ìpínlẹ̀")},
        )
    with pytest.raises(ValueError, match="unknown language"):
        dot(
            list(STATES5),
            [FIVE],
            title="T",
            value_label="v",
            category_label="State",
            source="S",
            translations={"xx": translation("ha")},
        )


def test_documents_without_translations_are_unchanged_in_shape() -> None:
    doc = dot(list(STATES5), [FIVE], title="T", value_label="v", category_label="State", source="S")
    assert "alt_text_translations" not in doc
    assert not [c for c in doc["audit"]["checks"] if "lang" in c]


@pytest.mark.parametrize("code", OTHERS)
def test_a_reversed_comparison_in_a_finding_fails(code: str) -> None:
    doc = dot_doc()
    f = LANGUAGES[code].FINDINGS
    bad = copy.deepcopy(doc)
    sentences = bad["alt_text_translations"][code]["findings"]
    k = next(i for i, s in enumerate(sentences) if f["higher"] in s)
    sentences[k] = sentences[k].replace(f["higher"], f["lower"], 1)
    bad["alt_text_translations"][code]["origin"] = "human"
    check = next(
        c
        for c in audit(bad)["checks"]
        if c["id"] == "alt-text-translation-matches-data" and c["lang"] == code
    )
    assert not check["passed"] and check["claim_problems"], sentences[k]


# Review 2026-11-06: adding languages must not make English-only names fail. "Ila" is an LGA
# (Osun, Kwara) and a Yoruba word; "Duk" and "Ka" are Hausa words.
@pytest.mark.parametrize("name", ["Ila", "Isi", "Oke", "Duk", "Ka", "Ihe", "Nke"])
def test_english_only_names_that_are_words_in_other_languages_still_build(name: str) -> None:
    data = ChartData(categories=(name, "Kano"), series=(Series("Share", (1.0, 2.0)),))
    describe(data, chart_type="bar", title="T", source="S")  # no error


def test_a_name_that_is_a_claim_word_in_the_language_written_is_refused() -> None:
    data = ChartData(categories=("Ila", "Kano"), series=(Series("Share", (1.0, 2.0)),))
    hits = [c for c in ("ha", "yo", "ig", "pcm") if _refuses(data, c)]
    assert hits, "'Ila' should be reserved in at least one of the new languages"
    with pytest.raises(ValueError):
        describe(data, chart_type="bar", title="T", source="S", lang=hits[0])


def _refuses(data: ChartData, lang: str) -> bool:
    try:
        check_reserved(data, lang)
    except ValueError:
        return True
    return False
