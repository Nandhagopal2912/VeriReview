from flask import Flask, abort, g, jsonify

app = Flask(__name__)


@app.delete("/admin/users/<int:user_id>")
def delete_user(user_id):
    g.db.delete_user(user_id)
    return jsonify({"deleted": user_id})
