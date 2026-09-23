def parse_age(value):
    if value is None:
        raise ValueError("age is required")
    return int(value)
