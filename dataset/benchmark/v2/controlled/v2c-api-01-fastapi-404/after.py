from fastapi import FastAPI, HTTPException

app = FastAPI()
ITEMS = {}


@app.get("/items/{item_id}")
def read_item(item_id: int):
    if item_id not in ITEMS:
        raise HTTPException(status_code=404, detail="item not found")
    return ITEMS[item_id]
