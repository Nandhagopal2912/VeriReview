import requests


class FetchError(Exception):
    pass


def fetch(url):
    try:
        response = requests.get(url, timeout=10)
    except Exception:
        pass
    return response.json()
