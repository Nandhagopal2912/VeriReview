class Mgr:
    def __init__(self, size):
        self.size = size


def default_pool():
    return Mgr(10)
