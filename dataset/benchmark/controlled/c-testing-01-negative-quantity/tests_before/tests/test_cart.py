from shop.cart import add_item


def test_add_item():
    assert add_item({}, "a", 2) == {"a": 2}
