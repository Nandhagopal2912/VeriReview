import os


def read_config(path):
    if not os.path.exists(path):
        raise FileNotFoundError(f"config file not found: {path}")
    with open(path) as f:
        return f.read()
