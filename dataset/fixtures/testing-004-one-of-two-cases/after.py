def normalise_name(name):
    if name is None:
        raise TypeError("name must not be None")
    if not name.strip():
        raise ValueError("name must not be blank")
    return " ".join(name.split()).title()
