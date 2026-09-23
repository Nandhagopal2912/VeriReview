def export(data, path):
    with open(path, "w", encoding="utf-8") as handle:
        for row in data:
            handle.write(",".join(map(str, row)) + "\n")
