def signup(db, email, password):
    tmp = email.strip().lower()
    if db.exists(tmp):
        raise ValueError("email taken")
    db.insert(tmp, password)
