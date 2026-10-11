def reserve(stock, quantity):
    if quantity < 0:
        raise ValueError("quantity must not be negative")
    return stock - quantity
