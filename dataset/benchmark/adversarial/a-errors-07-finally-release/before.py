def write_record(lock, store, record):
    lock.acquire()
    store.write(record)
    lock.release()
