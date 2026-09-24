def approve(order, limit):
    if order.total > limit:
        raise ValueError("over the credit limit")
    return True
