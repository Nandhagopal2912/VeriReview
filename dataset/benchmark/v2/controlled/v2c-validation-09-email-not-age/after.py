def register(email, age):
    if not email:
        raise ValueError("email is required")
    return {"email": email, "age": age}
