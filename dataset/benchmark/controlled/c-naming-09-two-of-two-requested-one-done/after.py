def scale(values, count, f):
    out = []
    for v in values[:count]:
        out.append(v * f)
    return out
