def process_payment(gateway, amount):
    response = gateway.charge(amount)
    return response.ok
