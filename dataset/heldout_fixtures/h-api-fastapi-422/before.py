from fastapi import HTTPException

from api.app import app


@app.post("/orders")
def create_order(sku: str, quantity: int):
    return {"sku": sku, "quantity": quantity}
