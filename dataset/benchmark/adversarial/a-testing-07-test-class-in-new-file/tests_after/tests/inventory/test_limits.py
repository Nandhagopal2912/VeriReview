import pytest

from inventory.remove import remove_stock


class TestStockLimits:
    def test_removing_more_than_available_raises(self):
        with pytest.raises(ValueError, match="not enough stock"):
            remove_stock({"a": 1}, "a", 5)
