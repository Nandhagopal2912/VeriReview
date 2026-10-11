from flask import Flask, jsonify, request

app = Flask(__name__)
CART = []


@app.post("/cart")
def add_item():
    qty = request.json.get("qty")
    if qty is None:
        return jsonify({"error": "qty is required"}), 400
    CART.append(qty)
    return jsonify({"items": len(CART)})
