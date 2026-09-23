def line_total(price, quantity):
    if quantity < 0:
        raise ValueError("quantity must not be negative")
    return price * quantity
