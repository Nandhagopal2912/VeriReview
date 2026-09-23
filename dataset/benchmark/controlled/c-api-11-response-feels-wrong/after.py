from flask import Flask, jsonify

app = Flask(__name__)


@app.get("/status")
def status():
    return jsonify({"status": "ok", "version": "1.2"})
