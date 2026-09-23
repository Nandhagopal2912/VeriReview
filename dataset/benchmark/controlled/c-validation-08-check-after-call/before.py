import requests


def notify(url, payload):
    response = requests.post(url, json=payload, timeout=5)
    return response.status_code
