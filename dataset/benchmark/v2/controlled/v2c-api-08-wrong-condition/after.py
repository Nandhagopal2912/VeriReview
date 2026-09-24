from fastapi import FastAPI, HTTPException

app = FastAPI()
ORDERS = {}


@app.get("/orders/{order_id}")
def read_order(order_id: int):
    if order_id < 0:
        raise HTTPException(status_code=404)
    return ORDERS.get(order_id)
