class ConfigError(Exception):
    pass


def load_key(path):
    with open(path) as f:
        return f.read().strip()
