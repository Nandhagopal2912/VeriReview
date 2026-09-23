import pytest

from shop.cart import add_item


def test_add_item():
    assert add_item({}, "a", 2) == {"a": 2}


def test_negative_quantity_is_rejected():
    with pytest.raises(ValueError):
        add_item({}, "a", -1)
