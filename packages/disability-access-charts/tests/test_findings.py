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
from disability_access_charts.findings import benjamini_hochberg, difference_p

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
    loose = make(reference=NATIONAL, fdr_q=0.2)["findings"]["supported"]
    strict = make(reference=NATIONAL, fdr_q=0.0001)["findings"]["supported"]
    assert strict < loose


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
        "Taraba, 11.3%, Abia, 10.6%, and Kano, 4.6%, are each higher than Nigeria as a "
        "whole, 3.0%.",
        "Oyo, 0.9%, and Lagos, 0.8%, are each lower than Nigeria as a whole, 3.0%.",
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
