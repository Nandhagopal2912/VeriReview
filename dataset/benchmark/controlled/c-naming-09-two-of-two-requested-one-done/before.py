def scale(values, n, f):
    out = []
    for v in values[:n]:
        out.append(v * f)
    return out
