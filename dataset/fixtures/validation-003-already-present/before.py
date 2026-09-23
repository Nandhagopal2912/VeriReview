def reserve(stock, sku, quantity):
    if quantity <= 0:
        raise ValueError("quantity must be positive")
    available = stock.get(sku, 0)
    if quantity > available:
        raise ValueError("not enough stock")
    stock[sku] = available - quantity
    return stock[sku]
