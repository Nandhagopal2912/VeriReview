def search(index, query):
    hits = index.lookup(query)
    if not hits:
        return None
    return [h.doc for h in hits]
