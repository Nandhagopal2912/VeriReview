def save_email(db, email):
    db.emails.insert(email)
    return True
    if not email:
        raise ValueError("email required")
