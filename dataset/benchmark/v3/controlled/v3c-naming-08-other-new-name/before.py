RATES = {"eu": 4.0, "world": 9.5}


def calc(weight, zone):
    return RATES[zone] * weight


def quote(weight, zone):
    return {"shipping": calc(weight, zone)}
