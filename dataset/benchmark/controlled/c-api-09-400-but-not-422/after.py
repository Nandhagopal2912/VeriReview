from fastapi import FastAPI, HTTPException

app = FastAPI()


@app.post("/pets")
def add_pet(payload: dict):
    if not payload.get("name"):
        raise HTTPException(status_code=400, detail="name is required")
    return {"name": payload.get("name"), "age": payload.get("age")}
