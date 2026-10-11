from text.normalize import normalize


def test_strips_and_lowercases():
    assert normalize("  Hello ") == "hello"
