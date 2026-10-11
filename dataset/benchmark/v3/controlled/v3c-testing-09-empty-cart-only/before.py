def cart_total(items, code=None):
    total = sum(item["price"] * item["qty"] for item in items)
    if code == "SAVE10":
        total *= 0.9
    return round(total, 2)
