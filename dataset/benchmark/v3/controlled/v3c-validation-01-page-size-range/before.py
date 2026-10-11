def page(rows, number, page_size):
    start = (number - 1) * page_size
    return rows[start : start + page_size]
