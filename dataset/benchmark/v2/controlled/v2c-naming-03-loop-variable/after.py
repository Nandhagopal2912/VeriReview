def reserved(orders):
    total = 0
    for order in orders:
        if order.status == "reserved":
            total += order.quantity
    return total
