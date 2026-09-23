from cart.total import total


def test_total_of_positive_prices():
    assert total([1, 2]) == 3
