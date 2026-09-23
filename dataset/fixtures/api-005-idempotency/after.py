from flask import jsonify, request

from web.app import app
from web import store


@app.post("/payments")
def create_payment():
    body = request.get_json()
    existing = store.find_payment_by_order(body["order_id"])
    if existing is not None:
        return jsonify(existing), 200
    payment = store.create_payment(body["order_id"], body["amount"])
    return jsonify(payment), 201
