def bulk_insert(table, ids):
    for row_id in ids:
        table.insert(row_id)
    return len(ids)
