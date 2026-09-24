def format_currency(cents):
    return f"${cents / 100:.2f}"


def invoice_line(item):
    return f"{item.name}: {format_currency(item.cents)}"


def invoice_total(items):
    return format_currency(sum(i.cents for i in items))
