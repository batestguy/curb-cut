import pytest
from disability_access_charts import DEFAULT_THEMES, OKABE_ITO, SYMBOLS, contrast_ratio


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_every_series_colour_passes_on_its_background(scheme: str) -> None:
    theme = DEFAULT_THEMES[scheme]
    assert len(theme.series) >= 4
    for colour in theme.series:
        assert contrast_ratio(colour, theme.background) >= 3.0, colour
    assert len(set(theme.series)) == len(theme.series)


def test_series_colours_are_okabe_ito() -> None:
    palette = set(OKABE_ITO.values())
    for theme in DEFAULT_THEMES.values():
        assert set(theme.series) <= palette


def test_okabe_ito_colours_left_out_fail_on_white() -> None:
    light = DEFAULT_THEMES["light"]
    for name in ("orange", "sky_blue", "yellow"):
        assert contrast_ratio(OKABE_ITO[name], light.background) < 3.0
        assert OKABE_ITO[name] not in light.series


def test_symbols_are_distinct_and_cover_the_series() -> None:
    assert len(set(SYMBOLS)) == len(SYMBOLS)
    assert len(SYMBOLS) >= max(len(t.series) for t in DEFAULT_THEMES.values())


def test_site_tokens_still_match_the_themes() -> None:
    # site/src/style.css --flag-green / --highlight must equal mark / highlight.
    assert DEFAULT_THEMES["light"].mark == "#008751"
    assert DEFAULT_THEMES["light"].highlight == "#1b1464"
    assert DEFAULT_THEMES["dark"].mark == "#198754"
    assert DEFAULT_THEMES["dark"].highlight == "#ffe08a"
