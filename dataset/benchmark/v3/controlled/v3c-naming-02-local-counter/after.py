def call_with_retry(func, limit=3):
    retry_count = 0
    while True:
        try:
            return func()
        except ConnectionError:
            retry_count += 1
            if retry_count >= limit:
                raise
