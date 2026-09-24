def reserved(orders):
    total = 0
    for x in orders:
        if x.status == "reserved":
            total += x.quantity
    return total
