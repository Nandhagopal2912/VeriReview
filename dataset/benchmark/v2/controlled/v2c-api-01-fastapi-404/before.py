from fastapi import FastAPI

app = FastAPI()
ITEMS = {}


@app.get("/items/{item_id}")
def read_item(item_id: int):
    return ITEMS.get(item_id)
