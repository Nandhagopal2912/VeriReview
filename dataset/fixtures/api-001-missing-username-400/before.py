from flask import jsonify, request

from web.app import app
from web.store import create_user


@app.post("/users")
def post_user():
    body = request.get_json()
    user = create_user(body["username"])
    return jsonify(user), 201
