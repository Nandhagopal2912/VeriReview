def add_line(cart, sku, quantity, price):
    cart.lines.append((sku, quantity, price))
