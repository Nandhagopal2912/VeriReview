SUPPORTED = {"EUR", "USD", "GBP"}


def convert(amount, currency, rates):
    return amount * rates[currency]
