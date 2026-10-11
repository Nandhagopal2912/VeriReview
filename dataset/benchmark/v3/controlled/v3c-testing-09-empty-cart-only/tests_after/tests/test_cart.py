from shop.cart import cart_total


def test_empty_cart_costs_nothing():
    assert cart_total([]) == 0
