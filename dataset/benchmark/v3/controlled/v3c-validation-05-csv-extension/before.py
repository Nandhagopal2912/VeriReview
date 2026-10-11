def read_table(path):
    with open(path) as f:
        return [line.rstrip().split(",") for line in f]
