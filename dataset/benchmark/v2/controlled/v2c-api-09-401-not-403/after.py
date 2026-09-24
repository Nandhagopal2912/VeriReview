from flask import Flask, abort, jsonify, request

app = Flask(__name__)


@app.get("/admin/stats")
def stats():
    user = request.environ.get("user")
    if user is None:
        abort(401)
    return jsonify({"users": 10})
