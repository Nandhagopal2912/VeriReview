import requests
from flask import Flask, jsonify

app = Flask(__name__)


@app.get("/quote")
def quote():
    try:
        upstream = requests.get("https://quotes.example/today", timeout=3)
    except requests.ConnectionError:
        return jsonify({"error": "upstream unavailable"}), 500
    return jsonify(upstream.json())
