from shop.unit import unit_price


def test_unit_price():
    assert unit_price(pr=10, qty=2) == 5
