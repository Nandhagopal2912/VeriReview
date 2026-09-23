def create_account(db, username, password):
    if not username or len(username) < 3:
        raise ValueError("username too short")
    return db.accounts.insert(username=username, password=password)
