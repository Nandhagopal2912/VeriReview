def page(rows, offset, limit):
    if limit < 0:
        raise ValueError("limit must not be negative")
    return rows[offset:offset + limit]
