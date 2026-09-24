import json


class SettingsError(Exception):
    pass


def load_settings(path):
    with open(path) as f:
        return json.load(f)
