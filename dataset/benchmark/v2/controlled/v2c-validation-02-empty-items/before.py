def checkout(cart_id, items):
    total = sum(i.price for i in items)
    return {"cart": cart_id, "total": total}
