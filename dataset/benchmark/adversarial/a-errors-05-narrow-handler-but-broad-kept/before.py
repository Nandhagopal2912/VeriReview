def import_rows(rows, parse):
    out = []
    for row in rows:
        try:
            out.append(parse(row))
        except Exception:
            continue
    return out
