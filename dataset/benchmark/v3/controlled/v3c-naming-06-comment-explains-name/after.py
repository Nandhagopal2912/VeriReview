def get_status(session, url):
    # res is the response of the status endpoint
    res = session.get(url)
    if res.status_code != 200:
        return None
    return res.json()["status"]
