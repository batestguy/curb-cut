"""Claim-checker cases from the 0.1 review: false claims must not pass silently, and true
claims must not be rejected.

Default data: Kano 12.0, Lagos 8.0, Abuja 4.0, Ibadan 2.0 (percent, no intervals).

``ok`` means no problems at all; ``err`` at least one error; ``warn`` warnings but no
error; ``flag`` an error or a warning (never silent); ``pass`` no error (warnings allowed).
"""

import pytest
from disability_access_charts import ChartData, Series, check_alt_text, describe

D = ChartData(
    ("Kano", "Lagos", "Abuja", "Ibadan"),
    (Series("Rate", (12.0, 8.0, 4.0, 2.0)),),
    unit="percent",
    decimals=1,
    category_label="State",
)
# A and B separated (difference 3.0 > 2.83); A and C not (1.5).
CI = ChartData(
    ("A", "B", "C", "D"),
    (Series("P", (10.0, 7.0, 8.5, 2.0), (8.0, 5.0, 6.5, 1.0), (12.0, 9.0, 10.5, 3.0)),),
    unit="percent",
    decimals=1,
    category_label="Area",
)
# A is separated from the runner-up B, but not from the lower, wider C.
WIDE = ChartData(
    ("A", "B", "C"),
    (Series("P", (10.0, 9.0, 8.9), (9.8, 8.8, 5.9), (10.2, 9.2, 11.9)),),
    unit="percent",
    decimals=1,
)
SHARES = ChartData(("A", "B", "C"), (Series("n", (50, 30, 20)),), shares=True)


def outcome(text: str, data: ChartData) -> str:
    problems = check_alt_text(text, data)
    if not problems:
        return "ok"
    return "err" if any(p.severity == "error" for p in problems) else "warn"


def assert_outcome(text: str, data: ChartData, expected: str) -> None:
    got = outcome(text, data)
    if expected == "flag":
        assert got in ("err", "warn"), (text, got, check_alt_text(text, data))
    elif expected == "pass":
        assert got in ("ok", "warn"), (text, got, check_alt_text(text, data))
    else:
        assert got == expected, (text, got, check_alt_text(text, data))


# B1 negation: never silent, and never an error on a true sentence.
@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Kano is not higher than Lagos.", "flag"),
        ("Kano isn't higher than Lagos.", "flag"),
        ("Kano is never higher than Lagos.", "flag"),
        ("Kano is no higher than Lagos.", "flag"),
        ("Kano is not as high as Lagos.", "flag"),
        ("Kano is not the highest.", "flag"),
        ("Kano is hardly the largest.", "flag"),
        ("Kano is far from the highest.", "flag"),
        ("Lagos is not higher than Kano.", "warn"),
        ("Lagos is not the highest.", "warn"),
    ],
)
def test_negation(text: str, expected: str) -> None:
    assert_outcome(text, D, expected)


@pytest.mark.parametrize("text", ["A is not higher than C.", "C is not higher than A."])
def test_negation_with_intervals_warns(text: str) -> None:
    assert_outcome(text, CI, "warn")


# B2 ordinal words.
@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Lagos is the second highest.", "ok"),
        ("Lagos is second-highest.", "ok"),
        ("Abuja is the third highest.", "ok"),
        ("Kano is the second highest.", "err"),
        ("Kano is the third highest.", "err"),
        ("Kano is the second-highest state.", "err"),
        ("Abuja is the second lowest.", "ok"),
        ("Lagos ranks second.", "ok"),
        ("Kano ranks second.", "err"),
        ("Kano is number one.", "ok"),
        ("Lagos is number one.", "err"),
        ("Lagos is first.", "err"),
        ("Kano is #2.", "err"),
        ("Kano is the joint highest.", "warn"),
        ("Kano is tied for highest.", "flag"),
        ("Lagos is the runner-up.", "flag"),
        ("Lagos is one of the highest.", "warn"),
    ],
)
def test_ordinals(text: str, expected: str) -> None:
    assert_outcome(text, D, expected)


# B3 several names on a side: every pair is checked.
@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Kano is higher than Lagos and Abuja.", "ok"),
        ("Kano is higher than both Lagos and Abuja.", "ok"),
        ("Kano, Lagos and Abuja are all higher than Ibadan.", "ok"),
        ("Abuja is higher than Ibadan and Lagos.", "err"),
        ("Abuja is higher than Lagos and Ibadan.", "err"),
        ("Abuja and Kano are higher than Lagos.", "err"),
        ("Kano and Abuja are higher than Lagos.", "err"),
        ("Kano, Ibadan and Lagos are all higher than Abuja.", "err"),
        ("Ibadan is lower than Abuja and Kano.", "ok"),
        ("Lagos is lower than Kano but higher than Abuja.", "ok"),
        ("Kano is higher than Lagos but lower than Abuja.", "err"),
        ("Lagos has a lower rate than Kano, Abuja is higher than Lagos.", "err"),
        ("Lagos is twice Abuja and Ibadan.", "err"),
    ],
)
def test_several_names(text: str, expected: str) -> None:
    assert_outcome(text, D, expected)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("A is higher than B.", "ok"),
        ("A is higher than B and C.", "err"),
        ("A is higher than C and B.", "err"),
        ("A is higher than D and C.", "err"),
        ("A is higher than B and D.", "ok"),
    ],
)
def test_several_names_with_intervals(text: str, expected: str) -> None:
    assert_outcome(text, CI, expected)


# B4 chart-wide numbers only with their cue words.
@pytest.mark.parametrize(
    ("text", "data", "expected"),
    [
        ("Lagos has 4%.", D, "err"),
        ("Lagos has 4.0%.", D, "err"),
        ("Kano has 4 more than Abuja.", D, "err"),
        ("4 states.", D, "ok"),
        ("There are 4 states; Kano has 12.0%.", D, "ok"),
        ("A has 3.", SHARES, "err"),
        ("A has 100.", SHARES, "err"),
        ("Total: 100.", SHARES, "ok"),
        ("A is 100 in total.", SHARES, "err"),
        ("The total is 100; A has 50.", SHARES, "ok"),
        ("A has 50 (50.0% of the total).", SHARES, "ok"),
        ("A has 50 (30.0% of the total).", SHARES, "err"),
        ("A has 50, which is 50% of the total.", SHARES, "ok"),
        ("A has 1,000 people.", SHARES, "err"),
    ],
)
def test_chart_wide_numbers(text: str, data: ChartData, expected: str) -> None:
    assert_outcome(text, data, expected)


# B5 vocabulary: checked where possible, warned otherwise.
@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Lagos trails Kano.", "ok"),
        ("Kano trails Lagos.", "err"),
        ("Lagos is double Abuja.", "ok"),
        ("Abuja is double Lagos.", "err"),
        ("Abuja is triple Lagos.", "err"),
        ("Lagos lags Kano.", "ok"),
        ("Lagos beats Kano.", "warn"),
        ("Lagos outranks Kano.", "warn"),
        ("Lagos outperforms Kano.", "warn"),
        ("Lagos is as high as Kano.", "warn"),
        ("Lagos is similar to Kano.", "warn"),
        ("Lagos is comparable to Kano.", "warn"),
        ("Lagos is close to Kano.", "warn"),
        ("Lagos is roughly the same as Kano.", "flag"),
        ("Lagos is nearly as high as Kano.", "warn"),
        ("Lagos is almost Kano.", "warn"),
        ("Kano has eleven percent.", "warn"),
        ("Kano has twelve percent.", "warn"),
        ("Kano is three-fold Abuja.", "warn"),
        ("Kano is up to 3 times Abuja.", "warn"),
        ("Kano is more than twice Abuja.", "warn"),
        ("Kano and Lagos differ in many ways.", "warn"),
    ],
)
def test_vocabulary(text: str, expected: str) -> None:
    assert_outcome(text, D, expected)


def test_a_clause_naming_two_groups_without_a_claim_warns() -> None:
    problems = check_alt_text("Kano stands well apart from Lagos.", D)
    assert [p.kind for p in problems] == ["unchecked"]
    assert "Kano and Lagos" in problems[0].reason


@pytest.mark.parametrize(
    "text",
    ["Kano has 12.0% and Lagos has 8.0%.", "The rate in Kano is 12.0%.", "Kano, 12.0%."],
)
def test_lists_of_values_are_not_relations(text: str) -> None:
    assert_outcome(text, D, "ok")


# S1 an unqualified superlative needs separation from every other group.
def test_superlative_needs_separation_from_every_group() -> None:
    assert_outcome("A is the highest.", WIDE, "err")
    assert_outcome("A is higher than C.", WIDE, "err")
    assert_outcome("A is higher than B.", WIDE, "ok")
    assert_outcome("A has the highest estimate.", WIDE, "ok")


# S2 true two-extreme sentences pass; the false variant is still rejected.
@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Kano has the highest rate and Ibadan has the lowest.", "ok"),
        ("The highest is Kano and the lowest is Ibadan.", "ok"),
        ("Kano is highest and Ibadan lowest.", "ok"),
        ("Kano is the highest at 12.0% and Ibadan is the lowest at 2.0%.", "ok"),
        ("Kano has the highest rate (12.0%) and Ibadan the lowest (2.0%).", "ok"),
        ("Kano rate of 12% vs Lagos 8%.", "pass"),
        ("Kano has the highest rate and Abuja the lowest.", "err"),
        ("Kano is the highest, not Lagos.", "ok"),
        ("Kano has the highest rate, Lagos the second.", "ok"),
        ("Kano, rather than Lagos, has the highest rate.", "pass"),
    ],
)
def test_two_claims_in_one_sentence(text: str, expected: str) -> None:
    assert_outcome(text, D, expected)


# M3 ratios of negative values warn.
def test_ratio_of_negative_values_warns() -> None:
    neg = ChartData(("A", "B"), (Series("v", (-10.0, -5.0)),), unit="number", decimals=1)
    assert ("warning", "ratio") in [
        (p.severity, p.kind) for p in check_alt_text("A is twice B.", neg)
    ]


# S5 names that collide with the vocabulary are refused.
@pytest.mark.parametrize("name", ["Highest", "Total", "Twice", "Not", "the same", "Second"])
def test_reserved_names_are_refused(name: str) -> None:
    with pytest.raises(ValueError, match="rename it"):
        ChartData((name, "Lagos"), (Series("v", (1, 2)),))


def test_minus_zero_is_not_written() -> None:
    data = ChartData(
        ("A", "B"),
        (Series("v", (0.0, 5.0), (-0.0, 4.0), (1.0, 6.0)),),
        unit="percent",
        decimals=0,
    )
    alt = describe(data, title="T", source="S")
    assert "-0%" not in alt
    assert check_alt_text(alt, data) == []


# M2 the interval level comes from "N% CI" or "N% confidence", not the first percent sign.
def test_interval_level_ignores_other_percentages() -> None:
    from disability_access_charts.describe import difference_test

    odd = ChartData(
        ("A", "B"),
        (Series("P", (10.0, 5.0), (8.0, 3.0), (12.0, 7.0)),),
        unit="percent",
        decimals=1,
        interval_label="design effect 1.5%, 90% CI",
    )
    result = difference_test(odd, (0, 0), (0, 1))
    assert result is not None
    assert result[2] == pytest.approx(1.96 * (2 * (2 / 1.6448536) ** 2) ** 0.5, rel=1e-4)


# Re-review round: the second comparator after "and" reuses the subject (N1).
@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Ibadan is lower than Kano and higher than Abuja.", "err"),
        ("Ibadan is lower than Lagos and higher than Abuja.", "err"),
        ("Kano is higher than Abuja and lower than Lagos.", "err"),
        ("Ibadan is lower than Kano and higher than Abuja and Lagos.", "err"),
        ("Lagos is lower than Kano and higher than Abuja and Kano.", "err"),
        ("Lagos is lower than Kano and higher than Abuja and Ibadan and Kano.", "err"),
        ("Abuja is higher than Ibadan and lower than Lagos.", "ok"),
        ("Lagos is lower than Kano and higher than Abuja and Ibadan.", "ok"),
        ("Lagos is lower than Kano but it is higher than Abuja.", "ok"),
        ("Lagos is lower than Kano but it is higher than Kano.", "err"),
        ("Lagos lags Kano and trails Abuja.", "err"),
    ],
)
def test_second_comparator_reuses_the_subject(text: str, expected: str) -> None:
    assert_outcome(text, D, expected)


# N2: "and is / and has" with no new subject: the claim is about the first names.
@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Kano is higher than Lagos and has the highest rate.", "ok"),
        ("Kano is higher than Lagos and is the highest.", "ok"),
        ("Kano is higher than Lagos and is ranked 1st.", "ok"),
        ("Kano has 12.0% and is higher than Lagos.", "ok"),
        ("Abuja is lower than Kano and has the highest rate.", "err"),
        ("Lagos is lower than Kano and is the highest.", "err"),
        ("Kano is higher than Ibadan and is the lowest.", "err"),
        ("Kano is higher than Ibadan and has the lowest rate.", "err"),
        ("Lagos is higher than Ibadan and is ranked 1st.", "err"),
        ("Abuja has 4.0% and is higher than Kano.", "err"),
    ],
)
def test_elided_subject(text: str, expected: str) -> None:
    assert_outcome(text, D, expected)


# S1-S3: no silent pass for vague relations, unnamed new subjects or excluded names.
@pytest.mark.parametrize(
    "text",
    [
        "Kano is Lagos.",
        "Kano has the rate of Lagos.",
        "Kano rate is Lagos rate.",
        "Kano is in Lagos.",
        "Kano is with Lagos.",
        "Kano and Lagos have the rate.",
        "Kano, Lagos and the rest are higher than Abuja.",
        "Kano is higher than Ibadan but the national rate is higher than Abuja.",
        "Kano is higher than Lagos but not Abuja.",
    ],
)
def test_vague_relations_are_never_silent(text: str) -> None:
    assert_outcome(text, D, "flag")


# S4: natural sentences, and their false twins.
@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Rates range from 2.0% in Ibadan to 12.0% in Kano.", "pass"),
        ("Rates range from 2.0% in Kano to 12.0% in Ibadan.", "err"),
        (
            "Kano, Lagos, Abuja and Ibadan have rates of 12.0%, 8.0%, 4.0% and 2.0% respectively.",
            "ok",
        ),
        (
            "Kano, Lagos, Abuja and Ibadan have rates of 8.0%, 12.0%, 4.0% and 2.0% respectively.",
            "err",
        ),
        ("Kano, Lagos and Abuja have rates of 12.0%, 8.0%, 4.0% and 2.0% respectively.", "warn"),
        ("Lagos's rate is 8.0%, Abuja's is 4.0%.", "ok"),
        ("Lagos's rate is 4.0%, Abuja's is 8.0%.", "err"),
        ("All four states have rates between 2.0% and 12.0%.", "pass"),
        ("All four states have rates between 2.0% and 13.0%.", "err"),
        ("Lagos has a rate of 8.0%, which is lower than Kano's 12.0%.", "ok"),
        ("Lagos has a rate of 12.0%, which is lower than Kano's 8.0%.", "err"),
        ("Kano has the highest rate, 12.0%, and Ibadan, 2.0%, the lowest.", "ok"),
        ("Kano has the highest rate, 12.0%, and Ibadan, 4.0%, the lowest.", "err"),
    ],
)
def test_natural_sentences(text: str, expected: str) -> None:
    assert_outcome(text, D, expected)


# S5: spelled counts before the label are checked.
@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Of the four states, Kano is the highest.", "ok"),
        ("Ibadan is the lowest of the four states.", "ok"),
        ("Of the five states, Kano is the highest.", "err"),
        ("All three states are listed.", "err"),
    ],
)
def test_spelled_counts(text: str, expected: str) -> None:
    assert_outcome(text, D, expected)


# Minor: "X to Y" next to a name must be that name's (lower, upper), in order.
@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("A, 8.0% to 12.0%.", "ok"),
        ("A's interval is 12.0% to 8.0%.", "err"),
        ("A, 10.0% to 12.0%.", "err"),
    ],
)
def test_interval_pairs(text: str, expected: str) -> None:
    assert_outcome(text, CI, expected)


# Third review: elliptical agreement ("and so is X") is not understood, so it must warn.
@pytest.mark.parametrize(
    "text",
    [
        "Kano is higher than Lagos, and so is Abuja.",
        "Abuja is lower than Lagos, as is Kano.",
        "Kano is higher than Abuja; Lagos is too.",
        "Kano is higher than Abuja, and likewise Ibadan.",
    ],
)
def test_elliptical_agreement_is_flagged(text: str) -> None:
    assert outcome(text, D) != "ok"
