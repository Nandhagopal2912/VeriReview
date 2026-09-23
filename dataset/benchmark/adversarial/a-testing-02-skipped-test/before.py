def remove_stock(stock, sku, amount):
    if amount <= 0:
        raise ValueError("amount must be positive")
    if stock.get(sku, 0) < amount:
        raise ValueError("not enough stock")
    stock[sku] -= amount
    return stock[sku]
