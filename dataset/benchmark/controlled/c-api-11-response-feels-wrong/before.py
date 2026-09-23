from flask import Flask, jsonify

app = Flask(__name__)


@app.get("/status")
def status():
    return jsonify({"ok": True, "version": "1.2"})
