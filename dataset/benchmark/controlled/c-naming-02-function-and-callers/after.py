def calculate_shipping(weight, zone):
    base = 5.0 if zone == "domestic" else 15.0
    return base + 0.5 * weight


def quote(order):
    return calculate_shipping(order.weight, order.zone)


def bulk_quote(orders):
    return [calculate_shipping(o.weight, o.zone) for o in orders]
