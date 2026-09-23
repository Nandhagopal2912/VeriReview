def get_user(db, user_id):
    return db.users.find_one(id=user_id)


def get_profile(db, user_id):
    return get_user(db, user_id).profile
