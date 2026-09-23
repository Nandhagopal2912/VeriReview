def sliding(values, w, s):
    return [values[i:i + w] for i in range(0, len(values) - w + 1, s)]
