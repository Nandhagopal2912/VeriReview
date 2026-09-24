def fetch(session, url, timeout):
    return session.get(url, timeout=timeout)
