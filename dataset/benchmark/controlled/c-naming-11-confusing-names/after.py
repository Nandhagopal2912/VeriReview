def transform(rows, key, wanted):
    present = [r for r in rows if r[key] is not None]
    by_key = {r[key]: r for r in present}
    return by_key.get(wanted)
