import pytest

from shop.stock import reserve


def test_negative_quantity_is_rejected():
    with pytest.raises(ValueError):
        reserve(10, -1)
