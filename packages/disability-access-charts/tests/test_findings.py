"""Statistical findings: the families, Benjamini-Hochberg, precision, sentences and audit."""

import copy
import json
from typing import Any

import pytest
from disability_access_charts import (
    ChartData,
    Reference,
    Series,
    audit,
    bar,
    check_alt_text,
    dot,
    grouped_bar,
    statistical_findings,
)
from disability_access_charts.findings import benjamini_hochberg, benjamini_yekutieli, difference_p

NAMES = ["Taraba", "Abia", "Kano", "Oyo", "Lagos"]
VALUES = (11.3, 10.6, 4.6, 0.9, 0.8)
LOWER = (8.9, 8.4, 3.6, 0.5, 0.5)
UPPER = (14.1, 13.1, 5.7, 1.5, 1.2)
NATIONAL = Reference("Nigeria as a whole", 3.0, 2.8, 3.2)
KW: dict[str, Any] = {
    "title": "Disability by state (synthetic)",
    "value_label": "Adults with disability (%)",
    "category_label": "State",
    "source": "Synthetic",
}


def make(precision: tuple[str, ...] | None = None, **overrides: Any) -> dict[str, Any]:
    series = Series(KW["value_label"], VALUES, LOWER, UPPER, precision)
    kw = {"findings": True, **KW, **overrides}
    return dot(NAMES, [series], **kw)


def failed(doc: dict[str, Any]) -> set[str]:
    return {c["id"] for c in audit(doc)["checks"] if not c["passed"]}


def test_benjamini_hochberg_matches_the_textbook_example() -> None:
    # Benjamini & Hochberg (1995), worked by hand: m = 4, q = 0.05.
    p = [0.01, 0.04, 0.03, 0.005]
    adjusted = benjamini_hochberg(p)
    # Sorted: 0.005 (x4/1 = 0.02), 0.01 (x4/2 = 0.02), 0.03 (x4/3 = 0.04), 0.04 (x4/4).
    assert adjusted == pytest.approx([0.02, 0.04, 0.04, 0.02])
    assert benjamini_hochberg([]) == []
    assert benjamini_hochberg([0.9, 0.95]) == pytest.approx([0.95, 0.95])


def test_p_value_agrees_with_the_claim_checker_threshold() -> None:
    # At exactly 1.96 standard errors the two-sided p-value is 0.05.
    assert difference_p(1.96, 1.0) == pytest.approx(0.05, abs=1e-4)
    assert difference_p(0.0, 1.0) == 1.0
    assert difference_p(1.0, 0.0) == 0.0


def test_families_are_declared_and_every_comparison_counted() -> None:
    doc = make(reference=NATIONAL)
    f = doc["findings"]
    fams = {x["id"]: x for x in f["families"]}
    # Extremes: Taraba vs Abia, Lagos vs Oyo. Rankings: the other 2 neighbour pairs.
    # Outliers: 5 states vs the national figure. Gaps: none with one series.
    assert fams["extremes"]["checked"] == 2
    assert fams["rankings"]["checked"] == 2
    assert fams["outliers"]["checked"] == 5
    assert fams["gaps"]["checked"] == 0
    assert f["checked"] == 9 == len(f["comparisons"])
    assert f["supported"] == sum(c["supported"] for c in f["comparisons"])
    assert f["lines"]["count"] == f"9 comparisons checked, {f['supported']} supported."
    assert f["method"]["q"] == 0.05 and f["method"]["correction"] == "benjamini-hochberg"
    assert doc["audit"]["passed"] is True
    assert audit(json.loads(json.dumps(doc))) == doc["audit"]


def test_supported_means_bh_adjusted_p_at_most_q() -> None:
    f = make(reference=NATIONAL)["findings"]
    for c in f["comparisons"]:
        assert c["supported"] == (c["p_adjusted"] <= 0.05)
        if c["supported"]:
            assert c["difference"] > c["threshold"]  # so it also passes the checker
    # The neighbours at the extremes overlap: not supported.
    extremes = [c for c in f["comparisons"] if c["family"] == "extremes"]
    assert not any(c["supported"] for c in extremes)


def test_a_stricter_q_supports_fewer() -> None:
    loose = make(reference=NATIONAL)["findings"]["supported"]  # q = 0.05
    strict = make(reference=NATIONAL, fdr_q=0.001)["findings"]
    assert strict["supported"] < loose
    assert strict["method"]["q"] == 0.001
    assert "false discovery rate 0.1%" in strict["lines"]["method"]


def test_every_sentence_passes_the_claim_checker() -> None:
    doc = make(reference=NATIONAL)
    f = doc["findings"]
    assert f["statements"]
    plain = ChartData.from_dict(doc["data"])
    for st in f["statements"]:
        if st["family"] != "outliers":
            assert check_alt_text(st["text"], plain) == []
    outliers = [s["text"] for s in f["statements"] if s["family"] == "outliers"]
    assert outliers == [
        "Taraba, 11.3%; Abia, 10.6%; and Kano, 4.6%, are each higher than Nigeria as a "
        "whole, 3.0%.",
        "Oyo, 0.9%; and Lagos, 0.8%, are each lower than Nigeria as a whole, 3.0%.",
    ]
    check = next(c for c in doc["audit"]["checks"] if c["id"] == "findings-claims")
    assert check["passed"] is True


def test_review_findings_are_hedged_and_unreliable_ones_dropped() -> None:
    doc = make(
        precision=("reliable", "reliable", "review", "reliable", "unreliable"),
        reference=NATIONAL,
        withheld=["Kebbi"],
    )
    f = doc["findings"]
    # Lagos (unreliable) is in one extreme pair and one outlier comparison: both dropped.
    assert f["dropped"] == 2 == len(f["dropped_comparisons"])
    assert {d["reason"] for d in f["dropped_comparisons"]} == {"unreliable"}
    assert not any("Lagos" in (c["a"]["category"], c["b"]["category"]) for c in f["comparisons"])
    assert f["lines"]["dropped"].startswith("2 more comparisons not tested")
    assert f["lines"]["withheld"].startswith("Not shown or compared (1): Kebbi")
    kano = [s for s in f["statements"] if "Kano" in s["text"]]
    assert kano and all(s["hedged"] for s in kano)
    assert all("Read with care: Kano's estimate is flagged for review." in s["text"] for s in kano)
    assert doc["audit"]["passed"] is True
    # The table shows the flags.
    assert doc["table"]["columns"][-1]["label"] == "Precision"
    assert doc["table"]["rows"][2][-1] == "Review: few events"


def test_no_supported_comparison_says_so() -> None:
    wide = Series("v", (5.0, 4.0), (1.0, 0.5), (9.0, 8.0))
    doc = dot(["Kano", "Lagos"], [wide], findings=True, **{**KW, "value_label": "v"})
    f = doc["findings"]
    assert f["supported"] == 0 and f["statements"] == []
    assert f["lines"]["none"] == "None of the comparisons is supported."
    assert f["lines"]["count"] == "1 comparison checked, 0 supported."


def test_gaps_compare_series_in_the_same_category() -> None:
    women = Series("Women", (6.0, 1.0, 2.0), (5.0, 0.5, 1.5), (7.0, 1.5, 2.5))
    men = Series("Men", (3.0, 0.9, 2.1), (2.5, 0.5, 1.6), (3.5, 1.3, 2.6))
    doc = grouped_bar(["Kano", "Lagos", "Oyo"], [women, men], findings=True, **KW)
    f = doc["findings"]
    gaps = [c for c in f["comparisons"] if c["family"] == "gaps"]
    assert len(gaps) == 3
    texts = [s["text"] for s in f["statements"] if s["family"] == "gaps"]
    assert texts == ["Kano: Women, 6.0%, is higher than Men, 3.0%."]
    assert any(c["id"] == "independence" for c in f["caveats"])
    # The checker's independence warning is expected and covered by the caveat.
    unchecked = next(c for c in doc["audit"]["checks"] if c["id"] == "findings-unchecked-claims")
    assert unchecked["passed"] is True
    assert doc["audit"]["passed"] is True


def test_bar_findings_and_ties_at_the_top() -> None:
    doc = bar(
        ["Kano", "Lagos", "Oyo"],
        [5.0, 5.0, 1.0],
        lower=[4.5, 4.5, 0.5],
        upper=[5.5, 5.5, 1.5],
        unit="percent",
        findings=True,
        **KW,
    )
    f = doc["findings"]
    extremes = [c for c in f["comparisons"] if c["family"] == "extremes"]
    assert len(extremes) == 2  # Kano and Lagos each against Oyo
    texts = [s["text"] for s in f["statements"]]
    assert texts[0].startswith("Highest estimate: Kano and Lagos, each 5.0%, and the survey can")
    assert doc["audit"]["passed"] is True


def test_findings_are_off_by_default_and_need_intervals() -> None:
    doc = dot(NAMES, [Series("v", VALUES, LOWER, UPPER)], **{**KW, "value_label": "v"})
    assert "findings" not in doc
    assert "precision" not in doc["data"]["series"][0]
    with pytest.raises(ValueError, match="intervals"):
        dot(NAMES, {"v": VALUES}, findings=True, **{**KW, "value_label": "v"})
    with pytest.raises(ValueError, match="only with findings=True"):
        make(findings=False, reference=NATIONAL)


def test_bad_findings_input_is_refused() -> None:
    with pytest.raises(ValueError, match="q must be"):
        make(fdr_q=0)
    with pytest.raises(ValueError, match="withheld names are in the chart"):
        make(withheld=["Kano"])
    with pytest.raises(ValueError, match="reference label"):
        make(reference=Reference("Kano", 3.0, 2.8, 3.2))
    with pytest.raises(ValueError, match="for 1 series"):
        make(reference=Reference("Nigeria as a whole", (3.0, 3.1), (2.8, 2.9), (3.2, 3.3)))
    with pytest.raises(ValueError, match="words of the findings"):
        dot(
            ["Care", "Lagos"],
            [Series("v", (1.0, 2.0), (0.5, 1.5), (1.5, 2.5))],
            findings=True,
            **{**KW, "value_label": "v"},
        )
    with pytest.raises(ValueError, match="precision flag"):
        make(precision=("reliable", "maybe", "reliable", "reliable", "reliable"))


def test_statistical_findings_runs_on_chart_data() -> None:
    data = ChartData(
        categories=tuple(NAMES),
        series=(Series("v", VALUES, LOWER, UPPER),),
        unit="percent",
        decimals=1,
    )
    f = statistical_findings(data, reference=NATIONAL, q=0.05)
    assert f["checked"] == 9


# --- The audit catches a tampered block (break tests) -----------------------------------------


def test_audit_catches_wrong_counts() -> None:
    doc = make(reference=NATIONAL)
    bad = copy.deepcopy(doc)
    bad["findings"]["supported"] += 1
    assert "findings-counts" in failed(bad)
    bad = copy.deepcopy(doc)
    bad["findings"]["lines"]["count"] = "9 comparisons checked, 9 supported."
    assert "findings-counts" in failed(bad)
    assert audit(bad)["passed"] is False


def test_audit_catches_a_comparison_flipped_to_supported() -> None:
    doc = make(reference=NATIONAL)
    bad = copy.deepcopy(doc)
    k = next(i for i, c in enumerate(bad["findings"]["comparisons"]) if not c["supported"])
    bad["findings"]["comparisons"][k]["supported"] = True
    bad["findings"]["supported"] += 1
    bad["findings"]["families"][0]["supported"] += 1
    assert "findings-match-data" in failed(bad)


def test_audit_catches_a_cell_not_in_the_data() -> None:
    doc = make(reference=NATIONAL)
    bad = copy.deepcopy(doc)
    bad["findings"]["comparisons"][0]["a"]["category"] = "Kebbi"
    assert "findings-cite-data" in failed(bad)
    bad = copy.deepcopy(doc)
    bad["findings"]["comparisons"][0]["a"]["value"] = 99.0
    assert "findings-cite-data" in failed(bad)


def test_audit_catches_a_false_sentence() -> None:
    doc = make(reference=NATIONAL)
    bad = copy.deepcopy(doc)
    bad["findings"]["statements"].append(
        {
            "family": "rankings",
            "text": "Abia, 10.6%, is higher than Taraba, 11.3%.",
            "comparisons": [],
            "hedged": False,
        }
    )
    out = failed(bad)
    assert "findings-claims" in out and "findings-match-data" in out


def test_audit_catches_a_missing_hedge() -> None:
    doc = make(
        precision=("reliable", "reliable", "review", "reliable", "reliable"), reference=NATIONAL
    )
    bad = copy.deepcopy(doc)
    st = next(s for s in bad["findings"]["statements"] if s["hedged"])
    st["text"] = st["text"].split(" Read with care")[0]
    assert "findings-hedged" in failed(bad)


# --- 0.2 review fixes ------------------------------------------------------------------------


def test_only_the_checked_sentences_reserve_names() -> None:
    # Words of the count, method and left-out lines ("Rate", "Survey", "Data") are fine.
    names = ["Rate", "Survey", "Data", "Difference", "A"]
    series = Series(
        "v", (9.0, 7.0, 5.0, 3.0, 1.0), (8.5, 6.5, 4.5, 2.5, 0.5), (9.5, 7.5, 5.5, 3.5, 1.5)
    )
    doc = dot(names, [series], findings=True, **{**KW, "value_label": "v"})
    assert doc["findings"]["supported"] > 0
    assert doc["audit"]["passed"] is True
    # A word of a finding sentence ("care", "flagged") is still refused.
    for word in ("Care", "Flagged"):
        with pytest.raises(ValueError, match="words of the findings"):
            dot(
                [word, "Lagos"],
                [Series("v", (1.0, 2.0), (0.5, 1.5), (1.5, 2.5))],
                findings=True,
                **{**KW, "value_label": "v"},
            )


def test_q_above_the_checker_level_is_refused() -> None:
    with pytest.raises(ValueError, match=r"at most 0.05"):
        make(fdr_q=0.2)
    with pytest.raises(ValueError, match=r"at most 0.05"):
        make(fdr_q=0.051)
    assert make(fdr_q=0.05)["findings"]["method"]["q"] == 0.05


# Area A against Area B: p = 0.038, between 0.05 / m (m = 4) and 0.05. Uncorrected, the
# survey can show the difference; after Benjamini-Hochberg it cannot.
AREAS = ["Area A", "Area B", "Area C", "Area D", "Area E"]
EDGE = Series(
    "v", (10.0, 7.0, 6.8, 6.6, 6.5), (8.0, 5.0, 4.8, 4.6, 4.5), (12.0, 9.0, 8.8, 8.6, 8.5)
)
CAN = "the survey can show a difference from the next estimate, Area B"
CANNOT = "the survey cannot show a difference from the next estimate, Area B"


def test_alt_text_extremes_follow_the_corrected_findings() -> None:
    kw = {**KW, "value_label": "v"}
    on = dot(AREAS, [EDGE], findings=True, **kw)
    off = dot(AREAS, [EDGE], **kw)
    f = on["findings"]
    top = next(c for c in f["comparisons"] if c["family"] == "extremes")
    assert (top["a"]["category"], top["b"]["category"]) == ("Area A", "Area B")
    assert 0.05 / f["checked"] < top["p"] < 0.05
    assert top["p_adjusted"] > 0.05 and top["supported"] is False
    # 0.1 behaviour without findings (uncorrected test); the corrected result with them.
    assert CAN in off["alt_text"]
    assert CANNOT in on["alt_text"]
    assert on["audit"]["passed"] is True and off["audit"]["passed"] is True
    # The audit holds the alt-text to the findings: "can" against them is an error...
    bad = copy.deepcopy(on)
    bad["alt_text"] = bad["alt_text"].replace(CANNOT, CAN)
    assert "alt-text-matches-data" in failed(bad)
    # ... and without findings, "cannot" against the uncorrected test still is.
    bad = copy.deepcopy(off)
    bad["alt_text"] = on["alt_text"]
    assert "alt-text-matches-data" in failed(bad)


def test_zero_width_intervals_are_dropped_not_supported() -> None:
    # Area E: 0 events, interval 0 to 0. With a zero standard error it would be
    # "supported" against anything; it is dropped and counted instead.
    zero = Series(
        "v", (6.0, 5.0, 3.0, 1.0, 0.0), (5.0, 4.0, 2.0, 0.5, 0.0), (7.0, 6.0, 4.0, 1.5, 0.0)
    )
    doc = dot(AREAS, [zero], findings=True, **{**KW, "value_label": "v"})
    f = doc["findings"]
    assert {d["reason"] for d in f["dropped_comparisons"]} == {"zero-width"}
    assert f["dropped"] == 1  # Area E against Area D, the lowest against the next
    assert not any("Area E" in (c["a"]["category"], c["b"]["category"]) for c in f["comparisons"])
    assert "interval of zero width" in f["lines"]["dropped"]
    # The alt-text cannot claim the dropped extreme either.
    assert "the survey cannot show a difference from the next estimate, Area D" in doc["alt_text"]
    assert doc["audit"]["passed"] is True
    bad = copy.deepcopy(doc)
    moved = bad["findings"]["dropped_comparisons"].pop()
    del moved["reason"]
    tested = {"difference": 1.0, "threshold": 0.0, "p": 0.0, "p_adjusted": 0.0}
    bad["findings"]["comparisons"].append({**moved, **tested, "supported": False, "hedged": False})
    assert "findings-hedged" in failed(bad)


def test_ranking_findings_give_ranks_that_the_checker_checks() -> None:
    f = make(reference=NATIONAL)["findings"]
    texts = [s["text"] for s in f["statements"] if s["family"] == "rankings"]
    assert texts == [
        "Abia, the second-highest estimate (10.6%), is higher than Kano, the third-highest "
        "estimate (4.6%).",
        "Kano, the third-highest estimate (4.6%), is higher than Oyo, the second-lowest "
        "estimate (0.9%).",
    ]
    plain = ChartData(
        categories=tuple(NAMES),
        series=(Series("v", VALUES, LOWER, UPPER),),
        unit="percent",
        decimals=1,
    )
    # A wrong rank is an error.
    wrong = texts[0].replace("second-highest", "third-highest", 1)
    assert any(p.kind == "rank" and p.severity == "error" for p in check_alt_text(wrong, plain))
    # Unhedged, a rank the test cannot separate from a neighbour (Abia from Taraba) warns;
    # hedged ("estimate") it does not, as for superlatives.
    unhedged = "Abia, the second-highest (10.6%), is higher than Kano, 4.6%."
    assert any(p.kind == "rank" for p in check_alt_text(unhedged, plain))
    assert check_alt_text(texts[0], plain) == []


def test_ordinals() -> None:
    from disability_access_charts._lang import en

    got = [en.ordinal(n) for n in (1, 2, 10, 11, 12, 13, 21, 22, 23, 37, 111)]
    want = ["first", "second", "tenth", "11th", "12th", "13th", "21st", "22nd", "23rd"]
    assert got == [*want, "37th", "111th"]


def test_outlier_lists_are_checked_item_by_item() -> None:
    # Semicolons between "name, value" items keep the list one clause: a wrong middle item
    # is caught (with commas, ", and" ended the subject and only the last name was checked).
    data = ChartData(
        categories=("Area A", "Area B", "Area C", "Overall"),
        series=(Series("v", (11.3, 2.0, 4.6, 3.0), (8.9, 1.9, 3.6, 2.8), (14.1, 2.1, 5.7, 3.2)),),
        unit="percent",
        decimals=1,
    )
    text = "Area A, 11.3%; Area B, 2.0%; and Area C, 4.6%, are each higher than Overall, 3.0%."
    errs = [p for p in check_alt_text(text, data) if p.severity == "error"]
    assert [p.kind for p in errs] == ["comparison"] and "Area B (2.0%)" in errs[0].reason
    good = "Area A, 11.3%; and Area C, 4.6%, are each higher than Overall, 3.0%."
    assert check_alt_text(good, data) == []
    # A wrong number in the list is still caught, against its own name.
    assert any(p.severity == "error" for p in check_alt_text(good.replace("4.6", "4.9"), data))


def test_dependence_caveat_gives_the_by_count() -> None:
    f = make(reference=NATIONAL)["findings"]
    caveat = next(c["text"] for c in f["caveats"] if c["id"] == "dependence")
    assert "not proven" in caveat and "nominal" in caveat
    by = benjamini_yekutieli([c["p"] for c in f["comparisons"]])
    n_by = sum(
        1
        for c, p in zip(f["comparisons"], by, strict=True)
        if p <= 0.05 and c["difference"] > c["threshold"]
    )
    assert f"would support {n_by} of the {f['checked']}." in caveat
    assert n_by <= f["supported"]


# --- Independent checks of the numbers --------------------------------------------------------


def test_p_values_match_scipy() -> None:
    stats = pytest.importorskip("scipy.stats")
    for diff, sd in [(0.5, 1.0), (1.96, 1.0), (3.0, 1.2), (0.01, 2.0), (6.0, 1.0)]:
        assert difference_p(diff, sd) == pytest.approx(2 * stats.norm.sf(diff / sd), abs=1e-12)


def test_p_values_by_hand() -> None:
    # Known normal quantiles: z = 1.644854 gives 0.10, z = 2.575829 gives 0.01.
    assert difference_p(1.644854, 1.0) == pytest.approx(0.10, abs=1e-6)
    assert difference_p(2.575829, 1.0) == pytest.approx(0.01, abs=1e-6)
    assert difference_p(-2.575829, 1.0) == pytest.approx(0.01, abs=1e-6)


def test_bh_and_by_match_scipy() -> None:
    stats = pytest.importorskip("scipy.stats")
    import random

    rng = random.Random(7)
    for m in (1, 2, 5, 17, 40):
        p = [rng.random() ** 3 for _ in range(m)]
        bh = list(stats.false_discovery_control(p, method="bh"))
        by = list(stats.false_discovery_control(p, method="by"))
        assert benjamini_hochberg(p) == pytest.approx(bh)
        assert benjamini_yekutieli(p) == pytest.approx(by)


def test_by_by_hand() -> None:
    # m = 4, c(4) = 1 + 1/2 + 1/3 + 1/4 = 25/12; BH from the textbook example above.
    c = 25 / 12
    want = [0.02 * c, 0.04 * c, 0.04 * c, 0.02 * c]
    assert benjamini_yekutieli([0.01, 0.04, 0.03, 0.005]) == pytest.approx(want)


def test_false_supported_rate_under_the_global_null_stays_below_q() -> None:
    # Every area has the same true value; each estimate is noisy with a known standard
    # error, and its 95% interval is +-1.96 SE. Any supported comparison is a false one, and
    # under the global null the false discovery rate is the chance of any.
    import random

    rng = random.Random(20261029)
    names = ("Area A", "Area B", "Area C", "Area D", "Area E", "Area F")
    ref = Reference("Overall", 5.0, 4.9, 5.1)
    reps, any_false = 300, 0
    for _ in range(reps):
        se = [rng.uniform(0.3, 0.8) for _ in names]
        values = [round(5.0 + rng.gauss(0, s), 3) for s in se]
        lower = tuple(round(v - 1.96 * s, 3) for v, s in zip(values, se, strict=True))
        upper = tuple(round(v + 1.96 * s, 3) for v, s in zip(values, se, strict=True))
        data = ChartData(
            categories=names,
            series=(Series("v", tuple(values), lower, upper),),
            unit="number",
            decimals=3,
        )
        any_false += statistical_findings(data, reference=ref)["supported"] > 0
    assert any_false / reps < 0.05
