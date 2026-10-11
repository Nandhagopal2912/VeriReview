def chk(value):
    if value and len(value) < 80:
        return 1
    return 0


def clean(values):
    return [v for v in values if chk(v)]
