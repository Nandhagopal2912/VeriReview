def pack(items, boxes):
    if not items:
        return []
    box = boxes.new()
    for item in items:
        box.add(item)
    return [box]
