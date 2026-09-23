def save_order(db, order):
    db.orders.insert(order)
    return order.id
