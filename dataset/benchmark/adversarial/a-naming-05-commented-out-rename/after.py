def order_total(items):
    # total_price = 0
    tp = 0
    for item in items:
        tp += item.price * item.quantity
    return tp
