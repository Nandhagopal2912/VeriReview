from flask import jsonify, request

from web.app import app
from web.schema import check


@app.post("/forms")
def submit():
    errors = check(request.get_json())
    if errors:
        return jsonify({"errors": errors}), 400
    return jsonify({"ok": True}), 201
