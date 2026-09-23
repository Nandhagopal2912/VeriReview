import pytest

from accounts.validation import validate_username


def test_valid_username():
    assert validate_username(" alice ") == "alice"


def test_empty_username_is_rejected():
    with pytest.raises(ValueError):
        validate_username("")
