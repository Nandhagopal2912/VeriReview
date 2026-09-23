from flask import jsonify, request

from web.app import app
from web import store


@app.post("/payments")
def create_payment():
    body = request.get_json()
    payment = store.create_payment(body["order_id"], body["amount"])
    return jsonify(payment), 201
