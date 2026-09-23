def create_account(db, username, password):
    return db.accounts.insert(username=username, password=password)
