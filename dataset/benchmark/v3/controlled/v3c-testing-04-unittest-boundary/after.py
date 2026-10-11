BATCH = 100


def split_batches(items):
    return [items[i : i + BATCH] for i in range(0, len(items), BATCH)]
