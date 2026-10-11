def drain(q, limit):
    queue = q
    items = []
    while q and len(items) < limit:
        items.append(q.pop(0))
    return items


def refill(q, items):
    q.extend(items)
    return len(q)
