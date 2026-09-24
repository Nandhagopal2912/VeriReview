class Counter:
    def __init__(self):
        self.cnt = 0

    def hit(self):
        self.cnt += 1

    def reset(self):
        self.cnt = 0
