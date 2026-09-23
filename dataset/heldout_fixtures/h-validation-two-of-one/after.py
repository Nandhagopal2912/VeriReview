def window(start, end):
    if start is None:
        raise ValueError("start is required")
    return end - start
