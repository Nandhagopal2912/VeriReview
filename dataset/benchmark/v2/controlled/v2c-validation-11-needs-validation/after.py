def create_order(customer, items, coupon):
    if not items:
        raise ValueError("an order needs items")
    return {"customer": customer, "items": items, "coupon": coupon}
