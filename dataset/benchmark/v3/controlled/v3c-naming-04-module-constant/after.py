DEFAULT_TIMEOUT_S = 30


def fetch(session, url, timeout=DEFAULT_TIMEOUT_S):
    return session.get(url, timeout=timeout)


def ping(session, url):
    return session.head(url, timeout=DEFAULT_TIMEOUT_S / 3)
