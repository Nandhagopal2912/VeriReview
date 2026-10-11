def drain(queue, limit):
    items = []
    while queue and len(items) < limit:
        items.append(queue.pop(0))
    return items


def refill(queue, items):
    queue.extend(items)
    return len(queue)
