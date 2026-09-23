from users.checks import validate_email
from users.db import db


def register(email, name):
    db.save({"email": email, "name": name})
