def checkout(cart_id, items):
    if not items:
        raise ValueError("cannot check out an empty cart")
    total = sum(i.price for i in items)
    return {"cart": cart_id, "total": total}
