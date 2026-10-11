T = 30


def fetch(session, url, timeout=T):
    return session.get(url, timeout=timeout)


def ping(session, url):
    return session.head(url, timeout=T / 3)
