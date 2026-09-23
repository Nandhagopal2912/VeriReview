import threading

CACHE = {}
_LOCK = threading.Lock()


def remember(key, value):
    with _LOCK:
        CACHE[key] = value
