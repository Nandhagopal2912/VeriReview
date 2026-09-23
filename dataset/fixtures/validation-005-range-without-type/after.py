def set_age(person, age):
    if age < 0 or age > 150:
        raise ValueError("age must be between 0 and 150")
    person.age = age
    return person
