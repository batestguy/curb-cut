"""The alt-text generator and the number and claim checker."""

import pytest
from disability_access_charts import ChartData, Series, check_alt_text, describe
from disability_access_charts.describe import difference_test, errors, warnings

COUNTS = ChartData(
    categories=("Physical", "Hearing", "Visual", "Little stature"),
    series=(Series("Persons", (8186521, 7653482, 7187637, 61511)),),
    unit="count",
    shares=True,
    verbatim=("T", "S"),
    category_label="Type",
)

# Kano and Lagos overlap; Oyo and Ekiti are separated from the top two.
STATES = ("Kano", "Lagos", "Oyo", "Ekiti")
CI = ChartData(
    categories=STATES,
    series=(Series("Rate", (12.3, 11.9, 6.0, 4.1), (10.1, 9.8, 4.9, 3.0), (14.5, 14.0, 7.1, 5.2)),),
    unit="percent",
    decimals=1,
    verbatim=("T", "S"),
    category_label="State",
)
POINT = ChartData(
    categories=STATES,
    series=(Series("Rate", (12.3, 11.9, 6.0, 4.1)),),
    unit="percent",
    decimals=1,
    verbatim=("T", "S"),
    category_label="State",
)
TWO_SERIES = ChartData(
    categories=("Kano", "Lagos", "Oyo"),
    series=(
        Series("Women", (12.3, 11.9, 6.0), (10.1, 9.8, 4.9), (14.5, 14.0, 7.1)),
        Series("Men", (10.0, 9.0, 5.0), (8.0, 7.0, 4.0), (12.0, 11.0, 6.0)),
    ),
    unit="percent",
    decimals=1,
    verbatim=("T", "S"),
    category_label="State",
)


def ratio_data(a: float, b: float, *, interval: bool = False) -> ChartData:
    lower = (a - 0.2, b - 0.2) if interval else None
    upper = (a + 0.2, b + 0.2) if interval else None
    return ChartData(
        categories=("A", "B"),
        series=(Series("v", (a, b), lower, upper),),
        unit="number",
        decimals=2,
    )


def kinds(text: str, data: ChartData) -> list[tuple[str, str]]:
    return [(p.severity, p.kind) for p in check_alt_text(text, data)]


# --- Numbers --------------------------------------------------------------------------


def test_count_wording_is_unchanged_from_p1() -> None:
    alt = describe(COUNTS, title="T", source="S")
    assert alt == (
        "Bar chart: T. 4 bars, one per type. "
        "Largest: Physical, 8,186,521 (35.5% of the total). "
        "Smallest: Little stature, 61,511 (0.3% of the total). "
        "Total: 23,089,151. Source: S."
    )


def test_a_number_that_belongs_to_another_category_is_caught() -> None:
    alt = describe(COUNTS, title="T", source="S")
    swapped = alt.replace("Physical, 8,186,521", "Physical, 7,653,482")
    problems = errors(check_alt_text(swapped, COUNTS))
    assert [(p.number, p.reason) for p in problems] == [
        ("7,653,482", "belongs to Hearing, not Physical")
    ]


def test_a_number_not_in_the_data_is_caught() -> None:
    problems = errors(check_alt_text("Kano, 13.0%.", CI))
    assert [(p.number, p.reason) for p in problems] == [("13.0", "not in the data")]


def test_a_number_with_no_category_in_its_clause_is_caught() -> None:
    # A number in the data, but whose? A warning. A number in nobody's data: an error.
    problems = check_alt_text("Kano is shown; 12.3% is high.", CI)
    assert [(p.severity, p.kind) for p in problems] == [("warning", "number")]
    problems = errors(check_alt_text("Kano is shown; 13.3% is high.", CI))
    assert [p.reason for p in problems] == ["no category named in the clause"]


def test_rounding_to_the_written_decimals_is_allowed() -> None:
    assert errors(check_alt_text("Kano, 12%.", CI)) == []
    assert errors(check_alt_text("Kano, 12.30%.", CI)) == []
    assert errors(check_alt_text("Kano, 12.4%.", CI))


def test_interval_bounds_and_scale_words_are_read() -> None:
    assert errors(check_alt_text("Kano, 10.1% to 14.5%.", CI)) == []
    assert errors(check_alt_text("Physical: 8.2 million.", COUNTS)) == []
    assert errors(check_alt_text("Physical: 9.2 million.", COUNTS))


def test_numbers_in_verbatim_strings_are_skipped() -> None:
    data = ChartData(
        categories=("A", "B"),
        series=(Series("v", (1, 2)),),
        verbatim=("Survey 2021", "NBS 2023"),
    )
    assert errors(check_alt_text("Survey 2021: B, 2. Source: NBS 2023.", data)) == []


# --- Claims ---------------------------------------------------------------------------


def test_correct_claims_pass_without_intervals() -> None:
    for text in [
        "Kano is the highest.",
        "Ekiti has the lowest rate.",
        "Kano is higher than Lagos.",
        "Oyo has a lower rate than Lagos.",
        "Kano is twice Oyo.",
        "Oyo ranked 3 of 4.",
        "Lagos is 2nd.",
        "Ekiti is 1st lowest.",
    ]:
        assert check_alt_text(text, POINT) == [], text


def test_wrong_extreme_fails() -> None:
    problems = errors(check_alt_text("Lagos is the highest.", POINT))
    assert [p.kind for p in problems] == ["extreme"]
    assert "Kano" in problems[0].reason


def test_wrong_direction_fails() -> None:
    assert kinds("Lagos is higher than Kano.", POINT) == [("error", "comparison")]


def test_higher_fails_when_the_difference_interval_includes_zero() -> None:
    problems = check_alt_text("Kano is higher than Lagos.", CI)
    assert [(p.severity, p.kind) for p in problems] == [("error", "comparison")]
    assert problems[0].suggestion == "the survey cannot show a difference"
    # The same claim against a well-separated state passes.
    assert check_alt_text("Kano is higher than Ekiti.", CI) == []


def test_difference_test_formula() -> None:
    supported, diff, threshold = difference_test(CI, (0, 0), (0, 1)) or (None, 0, 0)
    se_kano, se_lagos = 2.2 / 1.96, 2.1 / 1.96  # larger half-widths: 14.5-12.3, 14.0-11.9
    assert diff == pytest.approx(0.4)
    assert threshold == pytest.approx(1.96 * (se_kano**2 + se_lagos**2) ** 0.5)
    assert supported is False


def test_interval_level_is_read_from_the_label() -> None:
    ninety = ChartData(
        categories=("A", "B"),
        series=(Series("v", (10.0, 13.0), (9.0, 12.0), (11.0, 14.0)),),
        unit="number",
        interval_label="90% confidence interval",
    )
    result = difference_test(ninety, (0, 0), (0, 1))
    assert result is not None
    se = 1.0 / 1.6448536
    assert result[2] == pytest.approx(1.96 * (2 * se**2) ** 0.5, rel=1e-4)


def test_twice_fails_at_ratio_1_7_and_passes_at_2_04() -> None:
    assert kinds("A is twice B.", ratio_data(1.7, 1.0)) == [("error", "ratio")]
    assert check_alt_text("A is twice B.", ratio_data(2.04, 1.0)) == []
    assert check_alt_text("A is 2 times B.", ratio_data(2.04, 1.0)) == []
    assert check_alt_text("B is half A.", ratio_data(2.04, 1.0)) == []
    assert kinds("A is three times B.", ratio_data(2.04, 1.0)) == [("error", "ratio")]


def test_a_ratio_with_intervals_needs_a_supported_difference() -> None:
    assert check_alt_text("A is twice B.", ratio_data(2.04, 1.0, interval=True)) == []
    wide = ChartData(
        categories=("A", "B"),
        series=(Series("v", (2.0, 1.0), (0.5, 0.1), (3.5, 1.9)),),
        unit="number",
    )
    assert kinds("A is twice B.", wide) == [("error", "ratio")]


@pytest.mark.parametrize(
    "text",
    [
        "There is no difference between Kano and Lagos.",
        "Kano and Lagos are not different.",
        "Kano is not statistically different from Lagos.",
        "Kano and Lagos do not differ.",
    ],
)
@pytest.mark.parametrize("data", [CI, POINT], ids=["intervals", "points"])
def test_no_difference_is_always_flagged(text: str, data: ChartData) -> None:
    problems = errors(check_alt_text(text, data))
    assert "no-difference" in [p.kind for p in problems]
    if data is CI:
        assert problems[0].suggestion == "the survey cannot show a difference"


def test_the_accepted_wording_is_checked_both_ways() -> None:
    assert check_alt_text("Kano: the survey cannot show a difference from Lagos.", CI) == []
    assert kinds("Kano: the survey can show a difference from Lagos.", CI) == [
        ("error", "difference")
    ]
    assert check_alt_text("Kano: the survey can show a difference from Ekiti.", CI) == []
    assert kinds("Kano: the survey cannot show a difference from Ekiti.", CI) == [
        ("error", "difference")
    ]


def test_equality() -> None:
    same = ChartData(categories=("A", "B"), series=(Series("v", (5, 5)),), unit="count")
    assert check_alt_text("A is the same as B.", same) == []
    assert kinds("Kano is the same as Lagos.", POINT) == [("error", "equality")]
    problems = errors(check_alt_text("Kano is the same as Lagos.", CI))
    assert [p.kind for p in problems] == ["equality"]
    assert problems[0].suggestion == "the survey cannot show a difference"


@pytest.mark.parametrize(
    "text",
    [
        "Kano exceeds Lagos.",
        "Kano has a greater rate than Lagos.",
        "Kano outnumbers Ekiti.",
        "The rate increased in Kano.",
        "Kano is significantly above Ekiti.",
        "Kano doubled.",
        "Kano is poorer than Lagos.",
        "Kano is the poorest.",
        "Kano is fourfold Ekiti.",
    ],
)
def test_unknown_comparatives_warn_and_never_pass_silently(text: str) -> None:
    problems = check_alt_text(text, POINT)
    assert problems, text
    assert ("warning", "unchecked") in [(p.severity, p.kind) for p in problems]


def test_unqualified_superlative_fails_with_intervals_but_the_hedge_passes() -> None:
    problems = errors(check_alt_text("Kano is the highest.", CI))
    assert [p.kind for p in problems] == ["extreme"]
    assert problems[0].suggestion == "Kano has the highest estimate"
    assert check_alt_text("Kano has the highest estimate.", CI) == []
    assert check_alt_text("Highest estimate: Kano, 12.3%.", CI) == []
    # Supported at the bottom: Ekiti is separated from Oyo.
    assert check_alt_text("Ekiti is the lowest.", CI) == []


def test_ranks() -> None:
    assert kinds("Oyo ranked 2 of 4.", POINT) == [("error", "rank")]
    assert kinds("Oyo ranked 3 of 5.", POINT) == [("error", "rank")]
    assert kinds("Lagos is 3rd highest.", POINT) == [("error", "rank")]
    assert check_alt_text("Lagos is 2nd highest.", POINT) == []
    assert check_alt_text("Oyo is 2nd lowest.", POINT) == []
    # Ties share a rank (competition ranking).
    tie = ChartData(categories=("A", "B", "C"), series=(Series("v", (5, 5, 1)),))
    assert check_alt_text("B ranked 1 of 3.", tie) == []
    assert kinds("C is 2nd.", tie) == [("error", "rank")]


def test_a_rank_with_overlapping_neighbours_warns() -> None:
    assert kinds("Lagos is 2nd.", CI) == [("warning", "rank")]
    assert check_alt_text("Oyo ranked 3 of 4.", CI) == []


def test_series_comparisons_warn_about_independence() -> None:
    problems = check_alt_text("In Oyo, Women are higher than Men.", TWO_SERIES)
    assert ("warning", "independence") in [(p.severity, p.kind) for p in problems]


def test_shares_warn_about_independence() -> None:
    data = ChartData(
        categories=("A", "B"),
        series=(Series("v", (70.0, 30.0), (65.0, 25.0), (75.0, 35.0)),),
        unit="percent",
        decimals=1,
        shares=True,
    )
    problems = check_alt_text("A is higher than B.", data)
    assert [(p.severity, p.kind) for p in problems] == [("warning", "independence")]


def test_unresolved_series_is_a_warning() -> None:
    problems = check_alt_text("Kano is higher than Lagos.", TWO_SERIES)
    assert [(p.severity, p.kind) for p in problems] == [("warning", "unchecked")]


# --- Generated text passes its own checker -------------------------------------------


def _bar(interval: bool) -> ChartData:
    return CI if interval else POINT


def _dot(interval: bool) -> ChartData:
    if interval:
        return TWO_SERIES
    return ChartData(
        categories=TWO_SERIES.categories,
        series=tuple(Series(s.name, s.values) for s in TWO_SERIES.series),
        unit="percent",
        decimals=1,
        verbatim=("T", "S"),
        category_label="State",
    )


@pytest.mark.parametrize("interval", [False, True], ids=["points", "intervals"])
@pytest.mark.parametrize("chart_type", ["bar", "dot"])
def test_generated_text_passes_its_own_checker(chart_type: str, interval: bool) -> None:
    data = _bar(interval) if chart_type == "bar" else _dot(interval)
    alt = describe(data, chart_type=chart_type, title="T", source="S")
    assert check_alt_text(alt, data) == [], alt


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
@pytest.mark.parametrize("chart_type", ["bar", "dot"])
def test_generated_text_passes_for_edge_cases(
    values: tuple[float, ...], interval: bool, chart_type: str
) -> None:
    cats = tuple(f"Group {chr(65 + i)}" for i in range(len(values)))
    series = Series(
        "Rate",
        values,
        tuple(v - 0.5 for v in values) if interval else None,
        tuple(v + 0.7 for v in values) if interval else None,
    )
    data = ChartData(categories=cats, series=(series,), unit="percent", decimals=1)
    alt = describe(data, chart_type=chart_type, title="T", source="S")
    assert check_alt_text(alt, data) == [], alt
    if chart_type == "dot":
        other = Series("Other", tuple(v + 0.3 for v in values), series.lower, None)
        if interval:
            other = Series(
                "Other",
                other.values,
                tuple(v - 0.4 for v in other.values),
                tuple(v + 0.4 for v in other.values),
            )
        multi = ChartData(categories=cats, series=(series, other), unit="percent", decimals=1)
        alt = describe(multi, chart_type="dot", title="T", source="S")
        assert check_alt_text(alt, multi) == [], alt


def test_generated_count_text_passes_with_ties_and_single_bars() -> None:
    for values in [(5, 5, 1), (7,), (3, 3, 3)]:
        data = ChartData(
            categories=tuple("ABC"[: len(values)]),
            series=(Series("n", values),),
            shares=True,
            verbatim=("T", "S"),
        )
        alt = describe(data, title="T", source="S")
        assert check_alt_text(alt, data) == [], alt


def test_interval_wording_is_hedged_and_states_the_test() -> None:
    alt = describe(CI, title="T", source="S")
    assert "Highest estimate: Kano, 12.3%, and the survey cannot show a difference" in alt
    assert "Lowest estimate: Ekiti, 4.1%, and the survey can show a difference" in alt
    assert "Intervals (95% confidence interval): Kano 10.1% to 14.5%" in alt
    assert "Highest:" not in alt
    # Summary first, detail second.
    assert alt.index("Highest estimate") < alt.index("Intervals")


def test_tampered_generated_claim_is_caught() -> None:
    alt = describe(CI, title="T", source="S")
    assert errors(check_alt_text(alt.replace("cannot show", "can show"), CI))
    assert errors(check_alt_text(alt.replace("Highest estimate", "Highest"), CI))


# --- Languages ----------------------------------------------------------------------


def test_unknown_language_raises() -> None:
    with pytest.raises(ValueError, match="unknown language"):
        describe(POINT, title="T", source="S", lang="ha")
    with pytest.raises(ValueError, match="unknown language"):
        check_alt_text("x", POINT, lang="yo")


def test_glossary_names_are_used_and_checked() -> None:
    data = ChartData(
        categories=("Kano", "Lagos"),
        series=(Series("Rate", (12.3, 11.9)),),
        unit="percent",
        decimals=1,
        glossary={"Kano": "Kano State"},
    )
    alt = describe(data, title="T", source="S")
    assert "Kano State, 12.3%" in alt
    assert check_alt_text(alt, data) == []


def test_round_trip_through_dict() -> None:
    assert ChartData.from_dict(CI.to_dict()) == CI


def test_warnings_helper() -> None:
    problems = check_alt_text("Kano exceeds Lagos.", POINT)
    assert warnings(problems) == problems
    assert errors(problems) == []


@pytest.mark.parametrize(
    "kwargs",
    [
        {"categories": (), "series": (Series("v", ()),)},
        {"categories": ("A", "A"), "series": (Series("v", (1, 2)),)},
        {"categories": ("A",), "series": (Series("v", (1, 2)),)},
        {"categories": ("A",), "series": (Series("v", (float("nan"),)),)},
        {"categories": ("A",), "series": (Series("v", (float("inf"),)),)},
        {"categories": ("A",), "series": (Series("v", (5,), (6,), (7,)),)},
        {"categories": ("A",), "series": (Series("v", (5,), (4,), None),)},
        {"categories": ("A",), "series": (Series("v", (-1,)),)},
        {"categories": ("A",), "series": (Series("v", (0,)),), "shares": True},
        {"categories": ("A",), "series": (Series("v", (1,)),), "unit": "ratio"},
        {"categories": ("A", "B"), "series": (Series("A", (1, 2)), Series("C", (1, 2)))},
    ],
)
def test_rejects_bad_data(kwargs: dict) -> None:
    with pytest.raises(ValueError):
        ChartData(**kwargs)
