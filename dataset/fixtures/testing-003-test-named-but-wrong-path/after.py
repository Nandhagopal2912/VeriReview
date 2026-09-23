import requests


def fetch_status(url, timeout=5):
    try:
        response = requests.get(url, timeout=timeout)
    except requests.Timeout:
        return None
    return response.status_code
