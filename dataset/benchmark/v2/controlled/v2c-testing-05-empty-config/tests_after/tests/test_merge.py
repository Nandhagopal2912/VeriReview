from app.merge import merge


def test_empty_overrides_keep_defaults():
    assert merge({"a": 1}, {}) == {"a": 1}
