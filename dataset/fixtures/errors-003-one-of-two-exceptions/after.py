import json

DEFAULTS = {"debug": False, "workers": 4}


def load_config(path):
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError:
        return dict(DEFAULTS)
