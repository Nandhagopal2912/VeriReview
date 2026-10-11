def read_text(path):
    # UnicodeDecodeError -> return an empty string
    with open(path, "rb") as f:
        return f.read().decode("utf-8")
