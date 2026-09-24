def rank(q, d):
    s = sum(1 for w in q.split() if w in d)
    return s / max(len(d), 1)
