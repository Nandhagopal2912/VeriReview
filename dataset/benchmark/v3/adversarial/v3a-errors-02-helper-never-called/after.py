def _safe_decode(data):
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return ""


def read_text(path):
    with open(path, "rb") as f:
        return f.read().decode("utf-8")
