def order_total(items):
    tp = 0
    for item in items:
        tp += item.price * item.quantity
    return tp
