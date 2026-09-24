from flask import Flask, jsonify, request

app = Flask(__name__)


@app.post("/comments")
def add_comment():
    data = request.get_json()
    if not data.get("text"):
        return jsonify({"error": "text is required"}), 400
    return jsonify({"text": data.get("text")}), 201
