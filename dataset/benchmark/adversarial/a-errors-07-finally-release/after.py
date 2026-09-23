def write_record(lock, store, record):
    lock.acquire()
    try:
        store.write(record)
    finally:
        lock.release()
