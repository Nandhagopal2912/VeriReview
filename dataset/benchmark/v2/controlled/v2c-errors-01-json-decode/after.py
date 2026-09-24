import json


def parse(text):
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {}
