from flask import jsonify, request

from web.app import app
from web.store import register


@app.post("/signup")
def signup():
    body = request.get_json()
    account = register(body["username"], body["password"])
    return jsonify(account), 201
