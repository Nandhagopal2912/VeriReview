def merge(paths, out):
    handles = [open(p) for p in paths]
    for h in handles:
        out.write(h.read())
    for h in handles:
        h.close()
