class Counter:
    def __init__(self):
        self.count = 0

    def hit(self):
        self.count += 1

    def reset(self):
        self.count = 0
