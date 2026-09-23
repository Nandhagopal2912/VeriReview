from flask import Flask, jsonify

app = Flask(__name__)
PROFILES = {}


@app.get("/profiles/<name>")
def profile(name):
    user = PROFILES.get(name)
    return jsonify(user)
