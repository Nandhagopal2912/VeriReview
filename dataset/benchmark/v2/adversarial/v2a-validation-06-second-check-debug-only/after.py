DEBUG = False


def transfer(source, target, amount):
    if amount <= 0:
        raise ValueError("amount must be positive")
    if DEBUG and source is target:
        raise ValueError("source and target must differ")
    source.balance -= amount
    target.balance += amount
