from fastapi import FastAPI, HTTPException

app = FastAPI()
USERS = {}


@app.post("/register")
def register(username: str, password: str):
    if username in USERS:
        raise HTTPException(status_code=409, detail="username already taken")
    USERS[username] = password
    return {"username": username}
