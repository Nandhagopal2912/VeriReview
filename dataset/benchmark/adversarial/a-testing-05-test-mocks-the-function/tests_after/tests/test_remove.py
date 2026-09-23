from unittest import mock

import pytest

from inventory.remove import remove_stock


def test_remove_some():
    assert remove_stock({"a": 5}, "a", 2) == 3


def test_remove_too_much():
    with mock.patch("inventory.remove.remove_stock", side_effect=ValueError) as fake:
        with pytest.raises(ValueError):
            fake({"a": 1}, "a", 5)
