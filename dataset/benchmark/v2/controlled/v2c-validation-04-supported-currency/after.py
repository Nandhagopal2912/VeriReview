SUPPORTED = {"EUR", "USD", "GBP"}


def convert(amount, currency, rates):
    if currency not in SUPPORTED:
        raise ValueError(f"unsupported currency {currency}")
    return amount * rates[currency]
