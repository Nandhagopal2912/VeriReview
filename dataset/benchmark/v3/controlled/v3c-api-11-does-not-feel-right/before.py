from fastapi import FastAPI

app = FastAPI()
USERS = {1: {"name": "Ada", "email": "ada@example.org"}}


@app.get("/profile/{user_id}")
def profile(user_id: int):
    user = USERS[user_id]
    return {"name": user["name"]}
