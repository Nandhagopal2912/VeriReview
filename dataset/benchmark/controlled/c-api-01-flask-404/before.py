from flask import Flask, jsonify

app = Flask(__name__)
ITEMS = {}


@app.get("/items/<int:item_id>")
def get_item(item_id):
    item = ITEMS.get(item_id)
    return jsonify(item)
