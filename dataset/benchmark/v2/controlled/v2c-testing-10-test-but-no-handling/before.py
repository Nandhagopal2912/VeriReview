import requests


def quote(url):
    return requests.get(url, timeout=2).json()["price"]
