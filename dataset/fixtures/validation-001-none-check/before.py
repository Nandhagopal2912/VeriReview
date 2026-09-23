from accounts.db import database


def save_user(username, email):
    record = {"username": username, "email": email}
    database.insert("users", record)
    return record
