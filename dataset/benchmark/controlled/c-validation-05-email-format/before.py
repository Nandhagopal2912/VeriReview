import re

EMAIL_RE = re.compile(r"[^@\s]+@[^@\s]+\.[a-z]{2,}")


def send_invite(mailer, email):
    mailer.send(email, "You're invited!")
