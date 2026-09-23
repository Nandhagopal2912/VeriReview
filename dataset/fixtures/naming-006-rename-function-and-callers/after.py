from orders.notifications import notify


def start_processing(order):
    order.status = "processing"
    return order


def handle_new_order(order):
    order = start_processing(order)
    notify(order)
    return order


def retry_order(order):
    return start_processing(order)
