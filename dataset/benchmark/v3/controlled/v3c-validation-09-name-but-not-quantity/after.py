def add_line(order, name, quantity):
    if not name:
        raise ValueError("name is required")
    order.append({"name": name, "quantity": quantity})
    return order
