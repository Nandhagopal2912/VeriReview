def span(start, end):
    if start > end:
        raise ValueError("start must be before end")
    return (end - start).days
