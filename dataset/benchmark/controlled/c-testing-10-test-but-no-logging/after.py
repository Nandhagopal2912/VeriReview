import requests


def fetch(url):
    try:
        return requests.get(url, timeout=3).json()
    except requests.Timeout:
        return None
