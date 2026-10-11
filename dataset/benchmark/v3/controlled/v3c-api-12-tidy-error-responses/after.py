ORDERS = {}


def cancel_order(order_id):
    order = ORDERS.get(order_id)
    if order is None:
        return {"error": "order not found"}
    if order["shipped"]:
        return "already shipped", 409
    order["cancelled"] = True
    return {"ok": True}
