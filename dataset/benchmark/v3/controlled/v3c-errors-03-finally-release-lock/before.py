def run_locked(lock, job):
    lock.acquire()
    result = job()
    lock.release()
    return result
