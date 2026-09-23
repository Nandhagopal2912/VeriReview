from flask import Flask, abort, jsonify

app = Flask(__name__)
ORDERS = {}


@app.get("/orders/<int:order_id>")
def get_order(order_id):
    order = ORDERS.get(order_id)
    if order is None:
        abort(404)
    return jsonify(order)
