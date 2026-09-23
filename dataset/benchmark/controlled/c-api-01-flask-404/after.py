from flask import Flask, abort, jsonify

app = Flask(__name__)
ITEMS = {}


@app.get("/items/<int:item_id>")
def get_item(item_id):
    item = ITEMS.get(item_id)
    if item is None:
        abort(404)
    return jsonify(item)
