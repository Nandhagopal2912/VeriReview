def read_text(path):
    try:
        with open(path) as f:
            return f.read()
    except FileNotFoundError:
        return None
