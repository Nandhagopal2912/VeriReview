import json

import requests


def fetch_rates(url):
    response = requests.get(url, timeout=5)
    try:
        return json.loads(response.text)
    except requests.RequestException:
        return {}
