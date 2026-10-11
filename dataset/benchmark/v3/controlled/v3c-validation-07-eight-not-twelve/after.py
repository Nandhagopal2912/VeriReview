def hash_password(password):
    return "hashed:" + password


def set_password(user, password):
    if len(password) < 8:
        raise ValueError("password is too short")
    user.password_hash = hash_password(password)
