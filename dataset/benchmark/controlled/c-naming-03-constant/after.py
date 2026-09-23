MAX_ITEMS = 50


def can_add(cart):
    return len(cart.items) < MAX_ITEMS


def remaining(cart):
    return MAX_ITEMS - len(cart.items)
