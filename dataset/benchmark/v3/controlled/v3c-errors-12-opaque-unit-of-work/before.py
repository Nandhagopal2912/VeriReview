def charge(ledger, gateway, account, amount):
    ledger.debit(account, amount)
    gateway.pay(account, amount)
