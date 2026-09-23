from users.db import db


def check_username(username):
    if not username:
        raise ValueError("username must not be empty")


def save(username):
    check_username(username)
    db.insert(username)
