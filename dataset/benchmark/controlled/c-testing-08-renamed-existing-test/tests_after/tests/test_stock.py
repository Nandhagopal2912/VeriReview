from inventory.stock import restock


def test_restock_adds_amount():
    assert restock({"a": 2}, "a", 3) == 5
