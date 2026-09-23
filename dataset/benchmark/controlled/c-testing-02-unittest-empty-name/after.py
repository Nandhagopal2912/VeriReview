def greeting(name):
    if not name:
        raise ValueError("name required")
    return f"Hello, {name}!"
