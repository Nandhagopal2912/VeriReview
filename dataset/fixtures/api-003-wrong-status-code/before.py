from flask import jsonify

from web.app import app
from web.store import find_order


@app.get("/orders/<order_id>")
def get_order(order_id):
    order = find_order(order_id)
    return jsonify(order), 200
