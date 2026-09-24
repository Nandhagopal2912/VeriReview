from text.greet import greet


def test_custom():
    assert greet("Ada", "Hi") == "Hi, Ada!"
