def charge(gateway, card, amount):
    result = gateway.charge(card, amount)
    return result.id
