def money(cents):
    sign = "-" if cents < 0 else ""
    return f"{sign}${abs(cents) / 100:.2f}"
