from fastapi import FastAPI, HTTPException

app = FastAPI()


@app.post("/pets")
def add_pet(payload: dict):
    return {"name": payload.get("name"), "age": payload.get("age")}
