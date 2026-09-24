class Queue:
    def __init__(self):
        self.items = []

    def process_items(self):
        return [i.run() for i in self.items]

    def drain(self):
        results = self.process_items()
        self.items.clear()
        return results
