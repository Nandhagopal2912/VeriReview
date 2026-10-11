def show(user):
    return {"name": user.name, "email": user.email}


def update(usr, fields):
    for key, value in fields.items():
        setattr(usr, key, value)
    return usr
