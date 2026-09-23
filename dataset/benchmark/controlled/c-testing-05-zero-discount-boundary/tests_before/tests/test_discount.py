from pricing.discount import discounted


def test_half_price():
    assert discounted(100, 50) == 50
