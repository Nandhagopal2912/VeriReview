from auth.tokens import is_valid


def test_token_is_valid():
    assert is_valid({"expires_at": 2000}, now=1000)
