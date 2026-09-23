from flask import Flask, jsonify, make_response, request

app = Flask(__name__)


@app.post("/rate")
def rate():
    stars = request.json.get("stars")
    if not 1 <= stars <= 5:
        error = make_response(jsonify({"error": "stars must be 1-5"}))
        error.status_code = 400
    return jsonify({"stars": stars})
