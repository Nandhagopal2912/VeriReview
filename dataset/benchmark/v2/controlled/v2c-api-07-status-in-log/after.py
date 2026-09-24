import logging

from flask import Flask, jsonify, request

app = Flask(__name__)
logger = logging.getLogger(__name__)
USERS = {}


@app.post("/login")
def login():
    user = USERS.get(request.json["user"])
    ok = user is not None and user.check(request.json["password"])
    if not ok:
        logger.info("401 for %s", request.json["user"])
    return jsonify({"ok": ok})
