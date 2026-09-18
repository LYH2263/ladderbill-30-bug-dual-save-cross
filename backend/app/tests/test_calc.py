import pytest

from app.engines.pair_compare import compare_pair
from app.engines.peak_compare import compare_plain_vs_peak
from app.engines.tier_progressive import calc_bill

TIERS = [{"up_to": 180, "price": 0.52}, {"up_to": 260, "price": 0.62}, {"up_to": None, "price": 0.82}]


def test_tier_first_band_only():
    r = calc_bill(120, TIERS, 1.0)
    assert r["total"] == 62.40
    assert len(r["segments"]) == 1


def test_tier_three_bands():
    r = calc_bill(400, TIERS, 1.0)
    assert r["total"] == 258.00
    assert len(r["segments"]) == 3


def test_peak_factor_multiplies_prices():
    plain = calc_bill(400, TIERS, 1.0)
    peak = calc_bill(400, TIERS, 1.2)
    assert peak["total"] == 309.60
    assert peak["total"] > plain["total"]


def test_compare_delta():
    c = compare_plain_vs_peak(400, TIERS, 1.2)
    assert c["plain_total"] == 258.00
    assert c["peak_total"] == 309.60
    assert c["delta"] == 51.60


def test_negative_kwh_raises():
    with pytest.raises(ValueError):
        calc_bill(-1, TIERS, 1.0)


def test_pair_delta_right_minus_left():
    r = compare_pair({"kwh": 400, "peak": False}, {"kwh": 400, "peak": True}, TIERS, 1.2)
    assert r["left"]["total"] == 258.00
    assert r["right"]["total"] == 309.60
    assert r["delta"] == 51.60
    assert len(r["left"]["segments"]) == 3
    assert len(r["right"]["segments"]) == 3


def test_pair_delta_negative_when_right_cheaper():
    r = compare_pair({"kwh": 400, "peak": True}, {"kwh": 120, "peak": False}, TIERS, 1.2)
    assert r["left"]["total"] == 309.60
    assert r["right"]["total"] == 62.40
    assert r["delta"] == -247.20


def test_pair_peak_flag_scales_only_that_side():
    r = compare_pair({"kwh": 120, "peak": False}, {"kwh": 120, "peak": True}, TIERS, 1.2)
    assert r["left"]["peak_factor"] == 1.0
    assert r["right"]["peak_factor"] == 1.2
