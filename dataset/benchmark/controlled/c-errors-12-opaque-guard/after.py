from orders.resilience import db_guard


def save_order(db, order):
    with db_guard():
        db.orders.insert(order)
    return order.id
