from fastapi import FastAPI, HTTPException

app = FastAPI()
USERS = {}


@app.post("/register")
def register(username: str, password: str):
    USERS[username] = password
    return {"username": username}
