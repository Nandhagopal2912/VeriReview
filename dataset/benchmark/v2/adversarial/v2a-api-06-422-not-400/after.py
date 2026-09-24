from fastapi import FastAPI, HTTPException

app = FastAPI()


@app.post("/signup")
def signup(payload: dict):
    email = payload.get("email")
    if email is not None and "@" not in email:
        raise HTTPException(status_code=422, detail="malformed email")
    return {"email": email}
