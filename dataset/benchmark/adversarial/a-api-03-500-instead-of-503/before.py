import requests
from flask import Flask, jsonify

app = Flask(__name__)


@app.get("/quote")
def quote():
    upstream = requests.get("https://quotes.example/today", timeout=3)
    return jsonify(upstream.json())
