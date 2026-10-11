def blend(a, b, ratio):
    if ratio < 0 or ratio > 1:
        raise ValueError("ratio must be between 0 and 1")
    return a * (1 - ratio) + b * ratio
