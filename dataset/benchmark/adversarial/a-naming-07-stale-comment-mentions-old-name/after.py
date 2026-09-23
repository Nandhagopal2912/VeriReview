def order_total(items):
    # TODO: tp is a bad name
    total_price = 0
    for item in items:
        total_price += item.price * item.quantity
    return total_price
