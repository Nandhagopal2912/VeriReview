from fastapi import FastAPI

app = FastAPI()


@app.post("/signup")
def signup(payload: dict):
    return {"email": payload.get("email")}
