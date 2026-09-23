from accounts.db import database


def save_user(username, email):
    if username is None:
        raise ValueError("username is required")
    record = {"username": username, "email": email}
    database.insert("users", record)
    return record
