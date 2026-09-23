def price_of(catalog, sku):
    item = catalog.get(sku)
    if item is None:
        raise KeyError(f"unknown SKU: {sku}")
    return item["price"]
