def rank(query, document):
    score = sum(1 for w in query.split() if w in document)
    return score / max(len(document), 1)
