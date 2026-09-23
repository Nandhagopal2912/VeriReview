def set_age(profile, age):
    if age < 0:
        raise ValueError("age must not be negative")
    profile.age = age
    profile.save()
