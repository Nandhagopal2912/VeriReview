from text.names import initials


def test_initials_of_empty_string():
    assert initials("") == ""
