def apply_discount(price, d):
    if d <= 0:
        return price
    return price * (1 - d)
