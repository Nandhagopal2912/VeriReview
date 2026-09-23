from orders.notifications import notify


def proc(order):
    order.status = "processing"
    return order


def handle_new_order(order):
    order = proc(order)
    notify(order)
    return order


def retry_order(order):
    return proc(order)
