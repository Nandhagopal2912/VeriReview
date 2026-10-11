from billing.db import unit_of_work


def charge(ledger, gateway, account, amount):
    with unit_of_work(ledger):
        ledger.debit(account, amount)
        gateway.pay(account, amount)
