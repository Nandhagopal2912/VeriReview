def page(rows, number, page_size):
    if not 1 <= page_size <= 100:
        raise ValueError("page_size must be between 1 and 100")
    start = (number - 1) * page_size
    return rows[start : start + page_size]
