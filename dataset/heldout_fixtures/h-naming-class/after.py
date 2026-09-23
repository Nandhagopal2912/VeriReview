class ConnectionManager:
    def __init__(self, size):
        self.size = size


def default_pool():
    return ConnectionManager(10)
