def transform(a, b, c):
    x = [r for r in a if r[b] is not None]
    y = {r[b]: r for r in x}
    return y.get(c)
