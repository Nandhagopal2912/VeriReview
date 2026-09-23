def save_user(db, username):
    if not username:
        raise ValueError("username must not be empty")
    db.insert("users", {"name": username})
