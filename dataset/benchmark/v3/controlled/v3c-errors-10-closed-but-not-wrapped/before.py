class ImportFailed(Exception):
    pass


def import_rows(path, sink):
    handle = open(path)
    for line in handle:
        sink.append(line.rstrip().split(","))
    handle.close()
