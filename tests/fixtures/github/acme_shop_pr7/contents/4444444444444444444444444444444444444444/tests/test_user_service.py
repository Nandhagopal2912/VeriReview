import pytest

from shop.user_service import save_user


def test_empty_username_rejected():
    with pytest.raises(ValueError):
        save_user(None, "")
