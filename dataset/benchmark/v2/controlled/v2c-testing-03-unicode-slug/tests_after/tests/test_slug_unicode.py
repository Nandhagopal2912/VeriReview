from text.slug import slug


def test_non_ascii_title():
    assert slug("Café Latte") == "cafe-latte"
