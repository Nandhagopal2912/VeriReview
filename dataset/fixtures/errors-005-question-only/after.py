import json


def parse_response(body):
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return None
    return data["result"]
