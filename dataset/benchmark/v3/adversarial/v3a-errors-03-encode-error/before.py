def read_text(path):
    with open(path, "rb") as f:
        return f.read().decode("utf-8")
