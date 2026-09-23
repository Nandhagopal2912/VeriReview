def apply_discount(price, d):
    if d < 0 or d > 1:
        raise ValueError("discount out of range")
    return price * (1 - d)
