from flask import jsonify, request

from web.app import app
from web.store import create_user


@app.post("/users")
def post_user():
    body = request.get_json() or {}
    username = body.get("username")
    if not username:
        return jsonify({"error": "username is required"}), 400
    user = create_user(username)
    return jsonify(user), 201
