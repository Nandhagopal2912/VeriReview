def fetch_invoices(client, month):
    return client.get(f"/invoices?month={month}")


def monthly_total(client, month):
    return sum(i["amount"] for i in get_data(client, month))
