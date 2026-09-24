def refund(order, amount):
    order.balance -= amount
    return order.balance
