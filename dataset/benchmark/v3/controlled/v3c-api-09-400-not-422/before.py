from flask import Flask, jsonify, request

app = Flask(__name__)
CART = []


@app.post("/cart")
def add_item():
    qty = request.json.get("qty")
    CART.append(qty)
    return jsonify({"items": len(CART)})
