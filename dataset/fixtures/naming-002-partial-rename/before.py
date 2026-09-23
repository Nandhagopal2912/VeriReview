def calc(items):
    tmp = 0
    for item in items:
        tmp += item.price * item.quantity
    return tmp


def checkout(cart):
    return calc(cart.items)
