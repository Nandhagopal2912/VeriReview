def refund(order, amount: float):
    order.balance -= amount
    return order.balance
