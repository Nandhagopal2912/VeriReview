def price_of(catalog, sku):
    item = catalog.get(sku)
    if item is None:
        return None
    return item["price"]
