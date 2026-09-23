from inventory.stock import restock


def test_restock():
    assert restock({"a": 2}, "a", 3) == 5
