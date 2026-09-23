import json


def parse_response(body):
    data = json.loads(body)
    return data["result"]
