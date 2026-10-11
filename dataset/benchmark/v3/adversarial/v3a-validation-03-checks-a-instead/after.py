def blend(a, b, ratio):
    if not 0 <= a <= 1:
        raise ValueError("a must be between 0 and 1")
    return a * (1 - ratio) + b * ratio
