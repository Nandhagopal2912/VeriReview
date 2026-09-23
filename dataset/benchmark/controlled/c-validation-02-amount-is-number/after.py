def top_up(wallet, amount):
    if not isinstance(amount, (int, float)):
        raise TypeError("amount must be a number")
    wallet.balance += amount
    return wallet.balance
