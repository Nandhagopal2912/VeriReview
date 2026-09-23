def apply_discount(price, discount):
    if discount <= 0:
        return price
    return price * (1 - discount)
