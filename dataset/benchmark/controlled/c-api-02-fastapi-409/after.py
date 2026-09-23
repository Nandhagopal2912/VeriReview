from fastapi import FastAPI, HTTPException

app = FastAPI()
USERS = {}


@app.post("/users")
def register(email: str):
    if email in USERS:
        raise HTTPException(status_code=409, detail="email already registered")
    USERS[email] = {"email": email}
    return USERS[email]
