import requests


def current_temperature(city):
    response = requests.get(f"https://weather.example/{city}", timeout=2)
    return response.json()["temp"]
