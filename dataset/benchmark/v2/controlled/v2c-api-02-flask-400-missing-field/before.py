from flask import Flask, jsonify, request

app = Flask(__name__)


@app.post("/comments")
def add_comment():
    data = request.get_json()
    return jsonify({"text": data.get("text")}), 201
