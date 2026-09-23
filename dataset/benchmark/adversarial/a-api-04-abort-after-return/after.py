from flask import Flask, abort, jsonify, request

app = Flask(__name__)


@app.post("/rate")
def rate():
    stars = request.json.get("stars")
    return jsonify({"stars": stars})
    if not 1 <= stars <= 5:
        abort(400)
