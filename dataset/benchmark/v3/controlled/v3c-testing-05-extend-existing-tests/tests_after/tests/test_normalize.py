from text.normalize import normalize


def test_strips_and_lowercases():
    assert normalize("  Hello ") == "hello"


def test_none_gives_empty_string():
    assert normalize(None) == ""
