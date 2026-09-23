def ship(order_id, customer_id, carrier):
    label = carrier.create_label(order_id)
    carrier.schedule(label, customer_id)
    return label
