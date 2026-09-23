def ship(order_id, customer_id, carrier):
    if customer_id is None:
        raise ValueError("customer_id is required")
    label = carrier.create_label(order_id)
    carrier.schedule(label, customer_id)
    return label
