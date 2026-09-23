from pricing.discount import discounted


def test_half_price():
    assert discounted(100, 50) == 50


def test_zero_discount_keeps_price():
    assert discounted(100, 0) == 100
