def charge(gateway, card, amount):
    try:
        result = gateway.charge(card, amount)
    except gateway.Declined:
        return None
    return result.id
