def read_table(path):
    if not path.endswith(".csv"):
        raise ValueError("expected a .csv file")
    with open(path) as f:
        return [line.rstrip().split(",") for line in f]
