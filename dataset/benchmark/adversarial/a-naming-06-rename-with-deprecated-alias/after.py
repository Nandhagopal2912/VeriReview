def fetch_user(db, user_id):
    return db.users.find_one(id=user_id)


# Deprecated alias, kept for external callers until the next major release.
get_user = fetch_user


def get_profile(db, user_id):
    return fetch_user(db, user_id).profile
