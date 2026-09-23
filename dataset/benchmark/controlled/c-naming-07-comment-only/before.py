def export_csv(lst, path):
    with open(path, "w") as f:
        for o in lst:
            f.write(f"{o.id},{o.total}\n")
