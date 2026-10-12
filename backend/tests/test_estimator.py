"""Estimator checked against hand calculations for a 40x60, 14 ft eave, 3/12 roof."""

import pytest

from app.estimator import EstimateInput, estimate


def lines(res, section):
    return {x.item: x for x in res.sections[section]}


@pytest.fixture()
def r():
    return estimate(EstimateInput(width_ft=40, length_ft=60))


def test_foundation(r):
    f = lines(r, "Slab & foundation")
    # slab 2400*4/12 = 800 cf; beam 200 LF * 1 ft * 20/12 ft = 333.3 cf; 1133.3/27 = 41.98 yd; *1.10 = 46.2 -> 46.5
    assert f["Concrete (slab + perimeter grade beam)"].qty == 46.5
    # grid: 27 bars x 60 ft + 41 bars x 40 ft = 3260; beam 4 x 200 = 800; 4060 * 1.1 / 20 = 223.3 -> 224
    assert f["#4 rebar"].qty == 224


def test_shell(r):
    s = lines(r, "Exterior shell (metal)")
    assert s["Roof panels"].qty == 42  # ceil(62 / 3) = 21 per side
    assert "21' 8\"" in s["Roof panels"].note  # 20.616 + 1 ft overhang
    assert s["Sidewall panels"].qty == 40
    assert s["Endwall panels"].qty == 28
    assert s["Wall area"].qty == 3000  # 200 LF * 14 + 2 gables of 100 sq ft
    assert s["Roof area"].qty == 2680
    assert s["Closure strips"].qty == 448  # 4 x 62 + 200


def test_foam_drywall_framing(r):
    foam = lines(r, "Spray foam insulation")
    assert foam["Spray foam, walls (closed cell)"].qty == 6600  # 3000 * 2 in * 1.1
    assert foam["Spray foam, roof deck (closed cell)"].qty == 8200  # 2473.9 * 3 * 1.1 = 8164 -> 8200
    dw = lines(r, "Drywall")
    assert dw["Drywall sheets (4x12)"].qty == 222  # (2000 + 5280 + 2400) * 1.1 / 48
    fr = lines(r, "Interior framing")
    assert fr["Wood studs (2x4)"].qty == 401  # (264 + 200) LF * 12/16 * 1.15


def test_partial_living_area_and_steel():
    r = estimate(EstimateInput(width_ft=40, length_ft=60, living_sqft=1600, framing="steel", insulation="open_cell"))
    assert r.summary["shop_sqft"] == 800
    fr = lines(r, "Interior framing")
    assert "Steel studs" in fr and "Steel track" in fr
    assert any("grommet" in a for a in r.assumptions)
    foam = lines(r, "Spray foam insulation")
    assert foam["Spray foam, walls (open cell)"].qty == 11600  # 3000 * 3.5 * 1.1 = 11550


def test_living_area_capped_at_footprint():
    r = estimate(EstimateInput(width_ft=30, length_ft=40, living_sqft=5000))
    assert r.summary["living_sqft"] == 1200 and r.summary["shop_sqft"] == 0
