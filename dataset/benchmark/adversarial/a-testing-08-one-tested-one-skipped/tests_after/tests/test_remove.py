import pytest

from inventory.remove import remove_stock


def test_remove_some():
    assert remove_stock({"a": 5}, "a", 2) == 3


def test_remove_too_much():
    with pytest.raises(ValueError):
        remove_stock({"a": 1}, "a", 5)


@pytest.mark.skip(reason="TODO")
def test_unknown_sku():
    with pytest.raises(ValueError):
        remove_stock({}, "zzz", 1)
