RATES = {"food": 0.0, "default": 0.2}


def tax(amount, kind):
    return amount * RATES.get(kind, RATES["default"])
