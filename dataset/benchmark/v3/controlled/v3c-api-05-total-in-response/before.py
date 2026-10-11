from fastapi import FastAPI

app = FastAPI()
ROWS = ["alpha", "beta", "gamma"]


@app.get("/search")
def search(q: str, limit: int = 10):
    rows = [r for r in ROWS if q in r]
    page = rows[:limit]
    return {"items": page}
