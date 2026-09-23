from users.checks import validate_email
from users.db import db


def register(email, name):
    validate_email(email)
    db.save({"email": email, "name": name})
