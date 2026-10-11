RATIO_ERROR = "ratio must be between 0 and 1"


def blend(a, b, ratio):
    return a * (1 - ratio) + b * ratio
