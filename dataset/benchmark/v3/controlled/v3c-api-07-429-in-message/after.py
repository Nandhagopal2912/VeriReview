from flask import Flask, jsonify

app = Flask(__name__)
COUNTS = {}
LIMIT = 20


@app.post("/messages/<user>")
def send_message(user):
    COUNTS[user] = COUNTS.get(user, 0) + 1
    if COUNTS[user] > LIMIT:
        return jsonify({"sent": False, "error": "429 rate limit exceeded"})
    return jsonify({"sent": True})
