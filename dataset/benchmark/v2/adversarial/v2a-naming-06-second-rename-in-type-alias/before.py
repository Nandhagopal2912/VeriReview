def length(pts, d):
    return sum(d(a, b) for a, b in zip(pts, pts[1:]))
