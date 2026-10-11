def get_status(session, url):
    res = session.get(url)
    if res.status_code != 200:
        return None
    return res.json()["status"]
