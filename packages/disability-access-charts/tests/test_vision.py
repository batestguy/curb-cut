"""Colour-vision simulation (Machado et al. 2009) and CIEDE2000."""

import pytest
from disability_access_charts.vision import (
    MACHADO_2009,
    SIMULATIONS,
    ciede2000,
    delta_e,
    neighbour_differences,
    simulate,
    to_lab,
)

# Pairs from Sharma, Wu and Dalal (2005), Table 1 (pairs 1-4, 17, 18).
SHARMA = [
    ((50.0, 2.6772, -79.7751), (50.0, 0.0, -82.7485), 2.0425),
    ((50.0, 3.1571, -77.2803), (50.0, 0.0, -82.7485), 2.8615),
    ((50.0, 2.8361, -74.0200), (50.0, 0.0, -82.7485), 3.4412),
    ((50.0, -1.3802, -84.2814), (50.0, 0.0, -82.7485), 1.0000),
    ((50.0, 2.5, 0.0), (73.0, 25.0, -18.0), 27.1492),
    ((50.0, 2.5, 0.0), (61.0, -5.0, 29.0), 22.8977),
]


@pytest.mark.parametrize(("lab1", "lab2", "want"), SHARMA)
def test_ciede2000_reproduces_sharma(lab1: tuple, lab2: tuple, want: float) -> None:
    assert ciede2000(lab1, lab2) == pytest.approx(want, abs=1e-4)
    assert ciede2000(lab2, lab1) == pytest.approx(want, abs=1e-4)


def test_lab_of_white_and_black() -> None:
    assert to_lab("#ffffff") == pytest.approx((100.0, 0.0, 0.0), abs=0.01)
    assert to_lab("#000000") == pytest.approx((0.0, 0.0, 0.0), abs=0.01)


def test_simulation_keeps_greys_and_merges_red_and_green() -> None:
    for m in MACHADO_2009.values():
        for row in m:
            assert sum(row) == pytest.approx(1.0, abs=1e-5)  # greys stay grey
    for vision in SIMULATIONS:
        assert simulate("#808080", vision) == "#808080"
    assert simulate("#2c7fb8", "normal") == "#2c7fb8"
    # A red and a green of similar lightness are far apart normally, almost the same for a
    # deuteranope, much closer for a protanope, and still apart for a tritanope.
    red, green = "#c37878", "#78a578"
    assert delta_e(red, green) > 40
    assert delta_e(red, green, "deuteranopia") < 5
    assert delta_e(red, green, "protanopia") < 15
    assert delta_e(red, green, "tritanopia") > 20
    with pytest.raises(ValueError, match="unknown colour vision"):
        simulate("#ffffff", "achromatopsia")


def test_neighbour_differences() -> None:
    d = neighbour_differences(["#ffffcc", "#a1dab4", "#41b6c4", "#2c7fb8", "#253494"])
    assert list(d) == list(SIMULATIONS)
    assert all(len(v) == 4 for v in d.values())
    assert min(min(v) for v in d.values()) == 10.3
