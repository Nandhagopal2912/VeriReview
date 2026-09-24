from datetime import date


def age(birthday, today=None):
    today = today or date.today()
    if birthday > today:
        raise ValueError("birthday is in the future")
    return today.year - birthday.year - ((today.month, today.day) < (birthday.month, birthday.day))
