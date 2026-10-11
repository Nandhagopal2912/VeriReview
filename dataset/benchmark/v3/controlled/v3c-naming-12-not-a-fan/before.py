class Store:
    def __init__(self):
        self.items = {}

    def proc(self, k):
        return self.items.pop(k, None)
