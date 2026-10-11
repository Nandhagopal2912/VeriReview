import contextlib


def read_text(path):
    with open(path, "rb") as f, contextlib.suppress(UnicodeDecodeError):
        return f.read().decode("utf-8")
    return ""
