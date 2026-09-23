from flask import Flask, jsonify, request

app = Flask(__name__)


@app.post("/rate")
def rate():
    stars = request.json.get("stars")
    if not 1 <= stars <= 5:
        return jsonify({"error": "stars must be 1-5"}), 400
    return jsonify({"stars": stars})
