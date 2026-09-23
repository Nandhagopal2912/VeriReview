def signup(db, email, password):
    normalized_email = email.strip().lower()
    if db.exists(normalized_email):
        raise ValueError("email taken")
    db.insert(normalized_email, password)
