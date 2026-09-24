from flask import Flask, jsonify

app = Flask(__name__)


@app.delete("/users/<int:user_id>")
def delete_user(user_id):
    return jsonify({"deleted": user_id})
