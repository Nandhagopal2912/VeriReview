FACTORS = {"km": 1000.0, "cm": 0.01}


def to_metres(value, unit):
    return FACTORS[unit] * value
