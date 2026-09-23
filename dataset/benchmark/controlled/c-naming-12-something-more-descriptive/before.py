def weekly(data):
    t = sum(d.value for d in data)
    m = t / len(data)
    return t, m
