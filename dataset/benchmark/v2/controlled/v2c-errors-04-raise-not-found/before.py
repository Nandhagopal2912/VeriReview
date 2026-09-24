class NotFoundError(Exception):
    pass


def index_of(items, name):
    for i, item in enumerate(items):
        if item.name == name:
            return i
    return -1
