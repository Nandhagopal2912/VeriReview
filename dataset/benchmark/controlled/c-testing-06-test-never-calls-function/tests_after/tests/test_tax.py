from shop.tax import RATES


def test_food_rate_is_zero():
    assert RATES["food"] == 0.0
