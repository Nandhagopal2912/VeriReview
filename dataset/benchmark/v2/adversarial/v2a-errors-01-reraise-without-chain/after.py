import json


class SettingsError(Exception):
    pass


def load_settings(path):
    try:
        with open(path) as f:
            return json.load(f)
    except json.JSONDecodeError:
        raise SettingsError(f"invalid settings file {path}") from None
