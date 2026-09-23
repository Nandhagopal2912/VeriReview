import logging

from flask import Flask, jsonify, request

app = Flask(__name__)
logger = logging.getLogger(__name__)


@app.post("/signup")
def signup():
    body = request.get_json()
    return jsonify({"email": body.get("email")}), 201
