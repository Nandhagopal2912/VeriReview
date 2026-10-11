def call_with_retry(func, limit=3):
    n = 0
    while True:
        try:
            return func()
        except ConnectionError:
            n += 1
            if n >= limit:
                raise
