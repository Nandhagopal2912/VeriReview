import csv


def read_rows(path):
    f = open(path, newline="")
    rows = list(csv.DictReader(f))
    f.close()
    return rows
