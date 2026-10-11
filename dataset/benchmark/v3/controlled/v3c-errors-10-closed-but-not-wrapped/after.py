class ImportFailed(Exception):
    pass


def import_rows(path, sink):
    handle = open(path)
    try:
        for line in handle:
            sink.append(line.rstrip().split(","))
    finally:
        handle.close()
