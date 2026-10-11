RATES = {"eu": 4.0, "world": 9.5}


def calculate(weight, zone):
    return RATES[zone] * weight


def quote(weight, zone):
    return {"shipping": calculate(weight, zone)}
