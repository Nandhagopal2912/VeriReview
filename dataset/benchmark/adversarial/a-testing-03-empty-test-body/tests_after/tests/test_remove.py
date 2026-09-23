from inventory.remove import remove_stock


def test_remove_some():
    assert remove_stock({"a": 5}, "a", 2) == 3


def test_remove_more_than_stock_raises_value_error():
    """Removing more than in stock raises ValueError."""
    pass
