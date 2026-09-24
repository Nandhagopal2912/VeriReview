import csv


def load(path):
    f = open(path)
    rows = list(csv.reader(f))
    return rows
