from users.db import db


def save(username):
    db.insert(username)
