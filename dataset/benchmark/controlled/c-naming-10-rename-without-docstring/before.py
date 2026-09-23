def proc(gateway, amount):
    response = gateway.charge(amount)
    return response.ok
