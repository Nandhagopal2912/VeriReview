from fastapi import HTTPException

from api.app import app


@app.post("/orders")
def create_order(sku: str, quantity: int):
    if quantity < 0:
        raise HTTPException(status_code=422, detail="quantity must not be negative")
    return {"sku": sku, "quantity": quantity}
