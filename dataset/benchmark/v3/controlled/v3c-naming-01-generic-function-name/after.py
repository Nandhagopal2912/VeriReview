def fetch_orders(client, since):
    return client.get("/orders", params={"since": since})


def daily_total(client, day):
    return sum(o["total"] for o in fetch_orders(client, day))


def has_orders(client, day):
    return bool(fetch_orders(client, day))
