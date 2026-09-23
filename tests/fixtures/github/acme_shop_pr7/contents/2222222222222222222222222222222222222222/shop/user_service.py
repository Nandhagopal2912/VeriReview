def save_user(db, username):
    db.insert("users", {"name": username})
