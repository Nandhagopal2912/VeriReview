def order_total(items):
    tp = 0
    for item in items:
        tp += item.price * item.quantity
    return tp


def refund_total(refunds):
    tp = 0
    for r in refunds:
        tp += r.amount
    return tp
