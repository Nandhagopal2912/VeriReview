FACTORS = {"km": 1000.0, "cm": 0.01}


def to_metres(value, unit):
    if unit not in FACTORS:
        raise KeyError(f"unknown unit {unit}")
    return FACTORS[unit] * value
