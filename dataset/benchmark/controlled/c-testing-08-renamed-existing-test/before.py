def restock(stock, sku, amount):
    stock[sku] = stock.get(sku, 0) + amount
    return stock[sku]
