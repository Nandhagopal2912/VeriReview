from fastapi import FastAPI

app = FastAPI()
USERS = {}


@app.post("/users")
def register(email: str):
    USERS[email] = {"email": email}
    return USERS[email]
