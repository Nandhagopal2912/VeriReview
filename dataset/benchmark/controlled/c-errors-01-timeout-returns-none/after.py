import requests


def current_temperature(city):
    try:
        response = requests.get(f"https://weather.example/{city}", timeout=2)
    except requests.Timeout:
        return None
    return response.json()["temp"]
