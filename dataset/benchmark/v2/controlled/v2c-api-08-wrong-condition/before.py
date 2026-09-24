from fastapi import FastAPI, HTTPException

app = FastAPI()
ORDERS = {}


@app.get("/orders/{order_id}")
def read_order(order_id: int):
    return ORDERS.get(order_id)
