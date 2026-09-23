from flask import Flask, jsonify, request

app = Flask(__name__)
MAX_BYTES = 1_000_000


@app.post("/upload")
def upload():
    if request.content_length and request.content_length > MAX_BYTES:
        return jsonify({"error": "file too large"}), 500
    return jsonify({"ok": True}), 201
