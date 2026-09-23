from flask import Flask, jsonify, request

app = Flask(__name__)


@app.post("/rate")
def rate():
    stars = request.json.get("stars")
    if not 1 <= stars <= 5:
        return jsonify({"error": "400 Bad Request: stars must be 1-5"})
    return jsonify({"stars": stars})
