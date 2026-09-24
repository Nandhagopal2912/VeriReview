def fmt(cents):
    return f"${cents / 100:.2f}"


def invoice_line(item):
    return f"{item.name}: {fmt(item.cents)}"


def invoice_total(items):
    return fmt(sum(i.cents for i in items))
