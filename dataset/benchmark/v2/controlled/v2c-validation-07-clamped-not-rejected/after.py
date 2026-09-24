def fetch(session, url, timeout):
    timeout = max(timeout, 0)
    return session.get(url, timeout=timeout)
