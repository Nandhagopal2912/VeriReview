def add_item(cart, sku, quantity):
    if quantity <= 0:
        raise ValueError("quantity must be positive")
    cart.setdefault(sku, 0)
    cart[sku] += quantity
    return cart
