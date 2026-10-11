def drain(q, limit):
    items = []
    while q and len(items) < limit:
        items.append(q.pop(0))
    return items


def refill(queue, items):
    queue.extend(items)
    return len(queue)
