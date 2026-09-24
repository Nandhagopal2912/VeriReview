def get_user(db, user_id):
    if not isinstance(user_id, int) or user_id <= 0:
        raise ValueError("user_id must be a positive integer")
    return db.query("SELECT * FROM users WHERE id = ?", user_id)
