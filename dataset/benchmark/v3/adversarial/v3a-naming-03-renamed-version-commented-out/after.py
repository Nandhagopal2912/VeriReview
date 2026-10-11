# def drain(queue, limit):
#     items = []
#     while queue and len(items) < limit:
#         items.append(queue.pop(0))
#     return items
def drain(q, limit):
    items = []
    while q and len(items) < limit:
        items.append(q.pop(0))
    return items


def refill(q, items):
    q.extend(items)
    return len(q)
