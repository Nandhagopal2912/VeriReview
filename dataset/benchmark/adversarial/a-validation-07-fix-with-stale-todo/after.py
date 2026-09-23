def refund(gateway, charge_id, amount):
    # TODO: validate amount
    if amount <= 0:
        raise ValueError("amount must be positive")
    return gateway.refund(charge_id, amount)
