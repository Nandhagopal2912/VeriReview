from flask import jsonify, request

from web.app import app
from web.store import register


@app.post("/signup")
def signup():
    body = request.get_json()
    username = body.get("username", "")
    if not username or len(username) > 32:
        raise ValueError("invalid username")
    account = register(username, body["password"])
    return jsonify(account), 201
