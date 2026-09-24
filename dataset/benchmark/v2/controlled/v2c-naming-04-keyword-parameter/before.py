def record(event, ts=None):
    return {"event": event, "at": ts}


def record_login(user):
    return record("login", ts=user.last_seen)
