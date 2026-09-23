import requests


class FetchError(Exception):
    pass


def fetch(url):
    response = requests.get(url, timeout=10)
    return response.json()
