def cached(cache, key):
    # may raise KeyError if the entry expired
    return cache[key]
