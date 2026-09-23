from http import HTTPStatus

from flask import Flask, jsonify, request

app = Flask(__name__)


@app.post("/rate")
def rate():
    stars = request.json.get("stars")
    if not isinstance(stars, int) or not 1 <= stars <= 5:
        return jsonify({"error": "stars must be 1-5"}), HTTPStatus.BAD_REQUEST
    return jsonify({"stars": stars})
