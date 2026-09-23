def apply_discount(price, rate):
    return round(price * (1 - rate), 2)


def calculate_tax(price, rate=0.2):
    return round(price * rate, 2)
