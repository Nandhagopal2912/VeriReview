from flask import Flask, abort, jsonify, request

app = Flask(__name__)


@app.get("/admin/stats")
def stats():
    user = request.environ.get("user")
    return jsonify({"users": 10})
