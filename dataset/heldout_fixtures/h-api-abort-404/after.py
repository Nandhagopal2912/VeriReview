from flask import abort, jsonify

from web.app import app
from web.store import load_user


@app.get("/users/<uid>")
def show(uid):
    user = load_user(uid)
    if user is None:
        abort(404)
    return jsonify(user.to_dict())
