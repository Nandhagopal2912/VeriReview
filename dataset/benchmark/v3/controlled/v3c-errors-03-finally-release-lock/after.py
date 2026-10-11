def run_locked(lock, job):
    lock.acquire()
    try:
        return job()
    finally:
        lock.release()
