import json


class ConfigError(Exception):
    pass


def load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)
