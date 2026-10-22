import json
import re
from typing import TypedDict

import pytest
from disability_access_charts.contrast import contrast_ratio
from disability_access_charts.experimental import (
    DEFAULT_THEMES,
    Theme,
    bar_chart,
    check_alt_text,
    describe_bar_chart,
)

# The module is deprecated; these tests pin its old behaviour, so hide the warning here.
pytestmark = pytest.mark.filterwarnings("ignore::DeprecationWarning")

CATS = ["Physical", "Hearing", "Visual", "Little stature"]
VALS = [8186521, 7653482, 7187637, 61511]


class Labels(TypedDict):
    title: str
    value_label: str
    category_label: str
    source: str


KW: Labels = {
    "title": "Persons with disabilities by type, Nigeria 2025",
    "value_label": "Persons",
    "category_label": "Disability type",
    "source": "JONAPWD 2025",
}


def _doc() -> dict:
    return bar_chart(CATS, VALS, **KW)


def test_document_is_json_serialisable_and_complete() -> None:
    doc = json.loads(json.dumps(_doc()))
    assert set(doc) >= {"plotly", "alt_text", "table", "audit", "meta", "themes"}
    assert doc["meta"]["experimental"] is True
    trace = doc["plotly"]["data"][0]
    assert trace["type"] == "bar"
    assert trace["x"] == VALS
    assert trace["y"] == CATS
    assert trace["hoverinfo"] == "skip"  # nothing may live only in a hover tooltip


def test_alt_text_states_the_facts() -> None:
    alt = _doc()["alt_text"]
    total = sum(VALS)
    assert alt.startswith("Bar chart: Persons with disabilities by type, Nigeria 2025.")
    assert "4 bars, one per disability type." in alt
    assert f"Largest: Physical, 8,186,521 ({100 * 8186521 / total:.1f}% of the total)" in alt
    assert f"Smallest: Little stature, 61,511 ({100 * 61511 / total:.1f}% of the total)" in alt
    assert f"Total: {total:,}." in alt
    assert alt.endswith("Source: JONAPWD 2025.")


def test_every_number_in_alt_text_is_recomputable_from_the_data() -> None:
    """Alt-text checked against the data: recompute each number independently."""
    doc = _doc()
    rows = doc["table"]["rows"]
    values = [r[1] for r in rows]
    total = sum(values)
    recomputed = {str(len(rows)), f"{total:,}"}
    recomputed |= {f"{v:,}" for v in values}
    recomputed |= {f"{100 * v / total:.1f}" for v in values}
    text = doc["alt_text"].replace(KW["title"], "").replace(KW["source"], "")
    numbers = re.findall(r"\d[\d,]*(?:\.\d+)?", text)
    assert numbers, "alt-text should contain numbers"
    assert all(n in recomputed for n in numbers), numbers


def test_check_alt_text_flags_a_wrong_number() -> None:
    alt = describe_bar_chart(CATS, VALS, title="T", category_label="Type", source="S")
    assert check_alt_text(alt, CATS, VALS, verbatim=("T", "S")) == []
    tampered = alt.replace("8,186,521", "8,186,999")
    assert check_alt_text(tampered, CATS, VALS, verbatim=("T", "S")) == ["8,186,999"]


def test_ties_are_named_together() -> None:
    alt = describe_bar_chart(
        ["A", "B", "C"], [5, 5, 1], title="T", category_label="Group", source="S"
    )
    assert "Largest: A and B, each 5 (45.5% of the total)" in alt


def test_table_matches_chart() -> None:
    table = _doc()["table"]
    assert table["caption"] == f"{KW['title']}. Source: {KW['source']}."
    assert [c["label"] for c in table["columns"]] == [
        "Disability type",
        "Persons",
        "Share of total (%)",
    ]
    assert [r[0] for r in table["rows"]] == CATS
    assert [r[1] for r in table["rows"]] == VALS
    assert sum(r[2] for r in table["rows"]) == pytest.approx(100, abs=0.2)


def test_audit_passes_with_default_themes() -> None:
    audit = _doc()["audit"]
    assert audit["passed"] is True
    ids = {(c["id"], c.get("theme")) for c in audit["checks"]}
    for theme in ("light", "dark"):
        assert ("wcag-1.4.11", theme) in ids
        assert ("wcag-1.4.3", theme) in ids
    assert ("alt-text-matches-data", None) in ids


def test_default_theme_ratios() -> None:
    light, dark = DEFAULT_THEMES["light"], DEFAULT_THEMES["dark"]
    assert light.mark == "#008751"  # Nigerian flag green
    assert contrast_ratio(light.mark, light.background) >= 4.5
    assert contrast_ratio(light.text, light.background) >= 4.5
    assert contrast_ratio(dark.mark, dark.background) >= 3.0
    assert contrast_ratio(dark.text, dark.background) >= 4.5


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_default_highlight_stands_out_from_bars_and_background(scheme: str) -> None:
    theme = DEFAULT_THEMES[scheme]
    assert theme.highlight is not None
    assert contrast_ratio(theme.highlight, theme.background) >= 3.0
    assert contrast_ratio(theme.highlight, theme.mark) >= 3.0


def test_audit_checks_the_highlight_against_background_and_bars() -> None:
    checks = _doc()["audit"]["checks"]
    highlight = [c for c in checks if c["description"].startswith("Highlight colour")]
    assert {(c["theme"], c["description"]) for c in highlight} == {
        ("light", "Highlight colour against background"),
        ("light", "Highlight colour against bar colour"),
        ("dark", "Highlight colour against background"),
        ("dark", "Highlight colour against bar colour"),
    }
    assert all(c["passed"] for c in highlight)


def test_audit_fails_for_a_highlight_too_close_to_the_bars() -> None:
    # A darker green is not enough: about 1.4:1 against the flag green.
    close = {
        "light": Theme(
            background="#ffffff", text="#000000", mark="#008751", grid="#ccc", highlight="#006b3f"
        )
    }
    audit = bar_chart(CATS, VALS, themes=close, **KW)["audit"]
    assert audit["passed"] is False
    failed = [c["description"] for c in audit["checks"] if not c["passed"]]
    assert failed == ["Highlight colour against bar colour"]


def test_theme_without_highlight_skips_the_highlight_checks() -> None:
    plain = {"light": Theme(background="#ffffff", text="#000000", mark="#008751", grid="#ccc")}
    checks = bar_chart(CATS, VALS, themes=plain, **KW)["audit"]["checks"]
    assert not [c for c in checks if c["description"].startswith("Highlight")]


def test_audit_fails_for_low_contrast_bars() -> None:
    yellow = {"light": Theme(background="#ffffff", text="#000000", mark="#f0e442", grid="#ccc")}
    audit = bar_chart(CATS, VALS, themes=yellow, **KW)["audit"]
    assert audit["passed"] is False
    failed = [c for c in audit["checks"] if not c["passed"]]
    assert [c["id"] for c in failed] == ["wcag-1.4.11"]


@pytest.mark.parametrize(
    ("cats", "vals"),
    [([], []), (["A"], [1, 2]), (["A", "B"], [1, -1]), (["A"], [0])],
)
def test_rejects_bad_input(cats: list[str], vals: list[int]) -> None:
    with pytest.raises(ValueError):
        bar_chart(cats, vals, **KW)


@pytest.mark.filterwarnings("default")
def test_experimental_functions_warn() -> None:
    with pytest.warns(DeprecationWarning, match="experimental.bar_chart is deprecated"):
        bar_chart(CATS, VALS, **KW)
