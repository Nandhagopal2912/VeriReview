def line_total(price, quantity):
    if quantity < 0:
        raise ValueError("quantity cannot be negative")
    return price * quantity
