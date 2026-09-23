import requests


def fetch_rates(url):
    # try:
    response = requests.get(url, timeout=5)
    # except requests.Timeout:
    #     return {}
    return response.json()
