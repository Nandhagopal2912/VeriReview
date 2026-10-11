def bulk_insert(table, ids):
    if len(set(ids)) != len(ids):
        raise ValueError("ids must be unique")
    for row_id in ids:
        table.insert(row_id)
    return len(ids)
