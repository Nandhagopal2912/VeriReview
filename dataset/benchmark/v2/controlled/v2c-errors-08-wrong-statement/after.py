import csv


def load(path):
    f = open(path)
    try:
        rows = list(csv.reader(f))
    except FileNotFoundError:
        rows = []
    return rows
