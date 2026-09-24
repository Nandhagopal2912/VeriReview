from flask import Flask, jsonify, request

app = Flask(__name__)


@app.post("/users/delete")
def delete_user():
    return jsonify({"deleted": request.json["id"]})
