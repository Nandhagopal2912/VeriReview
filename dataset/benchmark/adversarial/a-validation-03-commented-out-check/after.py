def save_email(db, email):
    # if not email:
    #     raise ValueError("email required")
    db.emails.insert(email)
