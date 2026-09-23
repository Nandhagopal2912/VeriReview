from inventory.remove import remove_stock


def test_remove_some():
    assert remove_stock({"a": 5}, "a", 2) == 3
