def hash_password(password):
    return "hashed:" + password


def set_password(user, password):
    user.password_hash = hash_password(password)
