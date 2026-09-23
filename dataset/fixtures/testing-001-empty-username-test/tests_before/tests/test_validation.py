from accounts.validation import validate_username


def test_valid_username():
    assert validate_username(" alice ") == "alice"
