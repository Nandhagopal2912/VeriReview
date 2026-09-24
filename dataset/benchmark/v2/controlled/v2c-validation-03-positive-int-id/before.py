def get_user(db, user_id):
    return db.query("SELECT * FROM users WHERE id = ?", user_id)
