def unit_price(pr, qty):
    if qty == 0:
        raise ValueError(f"price={pr} with zero quantity")
    return pr / qty
