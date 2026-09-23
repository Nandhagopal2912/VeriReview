def weekly(data):
    t = sum(d.value for d in data)
    mean = t / len(data)
    return t, mean
