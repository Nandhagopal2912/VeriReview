def apply_discount(price, d):
    # d is the discount_rate (a fraction between 0 and 1)
    if d < 0 or d > 1:
        raise ValueError("discount out of range")
    return price * (1 - d)
