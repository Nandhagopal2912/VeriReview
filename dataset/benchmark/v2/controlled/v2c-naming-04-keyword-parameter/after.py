def record(event, timestamp=None):
    return {"event": event, "at": timestamp}


def record_login(user):
    return record("login", timestamp=user.last_seen)
