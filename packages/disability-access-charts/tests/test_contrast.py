import pytest
from disability_access_charts import (
    contrast_ratio,
    passes_non_text,
    passes_text,
    relative_luminance,
)


def test_black_on_white_is_maximum() -> None:
    assert contrast_ratio("#000000", "#ffffff") == pytest.approx(21.0)


def test_identical_colours_are_minimum() -> None:
    assert contrast_ratio("#777777", "#777777") == pytest.approx(1.0)


def test_order_does_not_matter() -> None:
    assert contrast_ratio("#0072b2", "#ffffff") == contrast_ratio("#ffffff", "#0072b2")


def test_shorthand_hex_matches_full() -> None:
    assert relative_luminance("#fff") == relative_luminance("#ffffff")


def test_text_threshold_boundary() -> None:
    # #767676 on white is the well-known lightest grey that passes 4.5:1 (about 4.54).
    assert passes_text("#767676", "#ffffff")
    assert not passes_text("#777777", "#ffffff")


def test_large_text_uses_lower_threshold() -> None:
    # #949494 on white is about 3.03:1: fails normal text, passes large text.
    assert not passes_text("#949494", "#ffffff")
    assert passes_text("#949494", "#ffffff", large=True)


def test_okabe_ito_yellow_fails_non_text_on_white() -> None:
    assert not passes_non_text("#f0e442", "#ffffff")
    assert passes_non_text("#0072b2", "#ffffff")


@pytest.mark.parametrize("bad", ["red", "#12345", "#ggg", ""])
def test_rejects_invalid_colours(bad: str) -> None:
    with pytest.raises(ValueError):
        contrast_ratio(bad, "#ffffff")
