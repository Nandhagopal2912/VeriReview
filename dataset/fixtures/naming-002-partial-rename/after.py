def calc(items):
    total_price = 0
    for item in items:
        total_price += item.price * item.quantity
    return total_price


def checkout(cart):
    return calc(cart.items)
