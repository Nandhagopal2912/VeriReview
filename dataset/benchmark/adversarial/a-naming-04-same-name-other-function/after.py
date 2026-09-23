def order_total(items):
    tp = 0
    for item in items:
        tp += item.price * item.quantity
    return tp


def refund_total(refunds):
    total_price = 0
    for r in refunds:
        total_price += r.amount
    return total_price
