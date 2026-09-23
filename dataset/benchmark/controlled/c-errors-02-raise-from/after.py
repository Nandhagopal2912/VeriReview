import json


class ConfigError(Exception):
    pass


def load(path):
    try:
        with open(path) as f:
            return json.load(f)
    except json.JSONDecodeError as err:
        raise ConfigError(f"bad config file {path}") from err
