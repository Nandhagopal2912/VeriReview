from fastapi import FastAPI

app = FastAPI()
ACCOUNTS = []


@app.post("/accounts", status_code=201)
def create_account(name: str):
    ACCOUNTS.append({"name": name})
    return {"ok": True}
