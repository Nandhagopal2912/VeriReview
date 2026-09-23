import requests


def notify(url, payload):
    response = requests.post(url, json=payload, timeout=5)
    if not url.startswith("https://"):
        raise ValueError("webhook url must use https")
    return response.status_code
