def save_user(db, usr):
    """Persist a user record."""
    record = {"name": usr, "active": True}
    db.insert("users", record)
    return record
