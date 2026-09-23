def save_email(db, email):
    db.emails.insert(email)
