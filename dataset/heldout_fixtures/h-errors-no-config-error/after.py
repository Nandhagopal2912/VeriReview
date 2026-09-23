import json


class ConfigError(Exception):
    pass


def load(path):
    with open(path, encoding="utf-8") as fh:
        try:
            return json.load(fh)
        except json.JSONDecodeError as exc:
            print(f"bad config: {exc}")
            return {}
