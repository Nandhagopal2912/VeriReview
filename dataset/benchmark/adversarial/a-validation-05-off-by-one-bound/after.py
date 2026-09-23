def order(sku, quantity):
    if quantity < 0:
        raise ValueError("quantity must be at least 1")
    return {"sku": sku, "quantity": quantity}
