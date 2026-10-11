def read_text(path):
    with open(path, "rb") as f:
        try:
            return f.read().decode("utf-8")
        except UnicodeEncodeError:
            return ""
