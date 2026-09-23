import json

import requests


def fetch_rates(url):
    response = requests.get(url, timeout=5)
    return json.loads(response.text)
