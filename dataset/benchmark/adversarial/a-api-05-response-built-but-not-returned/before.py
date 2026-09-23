from flask import Flask, jsonify, request

app = Flask(__name__)


@app.post("/rate")
def rate():
    stars = request.json.get("stars")
    return jsonify({"stars": stars})
