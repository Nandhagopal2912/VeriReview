def ratio(a, b):
    if b == 0:
        raise ValueError("b must not be zero")
    return a / b


def percent(part, whole):
    return 100 * part / whole
