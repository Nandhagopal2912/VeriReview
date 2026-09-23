def payout(bank, account, amount):
    valid = amount > 0
    return bank.transfer(account, amount)
