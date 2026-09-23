from flask import jsonify

from web.app import app
from web.store import find_order


@app.get("/orders/<order_id>")
def get_order(order_id):
    order = find_order(order_id)
    if order is None:
        return jsonify({"error": "order not found"}), 400
    return jsonify(order), 200
