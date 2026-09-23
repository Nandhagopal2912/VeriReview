MAXN = 50


def can_add(cart):
    return len(cart.items) < MAXN


def remaining(cart):
    return MAXN - len(cart.items)
