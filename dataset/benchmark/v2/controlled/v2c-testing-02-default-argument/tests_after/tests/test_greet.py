from text.greet import greet


def test_custom():
    assert greet("Ada", "Hi") == "Hi, Ada!"


def test_default_greeting():
    assert greet("Ada") == "Hello, Ada!"
