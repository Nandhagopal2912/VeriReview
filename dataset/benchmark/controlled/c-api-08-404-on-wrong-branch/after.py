from flask import Flask, jsonify

app = Flask(__name__)
PROFILES = {}


@app.get("/profiles/<name>")
def profile(name):
    user = PROFILES.get(name)
    if user:
        return jsonify({"error": "not found"}), 404
    return jsonify(user)
