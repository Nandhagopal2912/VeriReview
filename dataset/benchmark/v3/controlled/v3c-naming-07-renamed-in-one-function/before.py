def show(usr):
    return {"name": usr.name, "email": usr.email}


def update(usr, fields):
    for key, value in fields.items():
        setattr(usr, key, value)
    return usr
