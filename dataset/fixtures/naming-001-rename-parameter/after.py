def save_user(db, username):
    """Persist a user record."""
    record = {"name": username, "active": True}
    db.insert("users", record)
    return record
