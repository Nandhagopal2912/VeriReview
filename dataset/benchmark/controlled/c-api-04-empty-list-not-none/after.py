def search(index, query):
    hits = index.lookup(query)
    if not hits:
        return []
    return [h.doc for h in hits]
