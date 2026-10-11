def get_data(client, since):
    return client.get("/orders", params={"since": since})


def daily_total(client, day):
    return sum(o["total"] for o in get_data(client, day))


def has_orders(client, day):
    return bool(get_data(client, day))
