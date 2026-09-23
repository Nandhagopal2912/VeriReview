EMAIL_REQUIRED = "email must be validated: it cannot be empty"


def save_email(db, email):
    db.emails.insert(email)
