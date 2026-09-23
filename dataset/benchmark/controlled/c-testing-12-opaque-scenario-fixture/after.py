def set_quantity(basket, sku, quantity):
    if quantity < 0:
        raise ValueError("negative quantity")
    basket[sku] = quantity
