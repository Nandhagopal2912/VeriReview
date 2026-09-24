def pick(table, key, idx):
    try:
        return table[key][idx]
    except KeyError:
        return None
