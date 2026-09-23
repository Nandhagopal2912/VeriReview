import re

EMAIL_RE = re.compile(r"[^@\s]+@[^@\s]+\.[a-z]{2,}")


def send_invite(mailer, email):
    if not EMAIL_RE.fullmatch(email):
        raise ValueError(f"invalid email: {email!r}")
    mailer.send(email, "You're invited!")
