def pack(items, boxes):
    box = boxes.new()
    for item in items:
        box.add(item)
    return [box]
