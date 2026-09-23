def export(rows, path):
    with open(path, "w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(",".join(map(str, row)) + "\n")
