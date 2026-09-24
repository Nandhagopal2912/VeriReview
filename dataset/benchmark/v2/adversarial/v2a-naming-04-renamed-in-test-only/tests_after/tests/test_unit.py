from shop.unit import unit_price


def test_unit_price():
    assert unit_price(price=10, qty=2) == 5
