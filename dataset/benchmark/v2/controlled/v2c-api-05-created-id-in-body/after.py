from fastapi import FastAPI

app = FastAPI()
ACCOUNTS = []


@app.post("/accounts", status_code=201)
def create_account(name: str):
    account = {"id": len(ACCOUNTS) + 1, "name": name}
    ACCOUNTS.append(account)
    return {"ok": True, "id": account["id"]}
