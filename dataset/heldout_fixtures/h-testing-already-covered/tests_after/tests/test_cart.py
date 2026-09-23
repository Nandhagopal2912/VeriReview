from cart.total import cart_total


def test_empty_cart_is_zero():
    assert cart_total([]) == 0
