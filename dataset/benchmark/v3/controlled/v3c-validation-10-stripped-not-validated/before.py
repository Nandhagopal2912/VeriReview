import re

EMAIL_RE = re.compile(r"[^@ ]+@[^@ ]+")


def save_email(user, email):
    user.email = email
    return user
