def validate_username(username):
    if not username:
        raise ValueError("username must not be empty")
    if len(username) > 32:
        raise ValueError("username too long")
    return username.strip()
