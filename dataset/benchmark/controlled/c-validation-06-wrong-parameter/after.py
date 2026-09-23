def add_line(cart, sku, quantity, price):
    if price <= 0:
        raise ValueError("price must be positive")
    cart.lines.append((sku, quantity, price))
