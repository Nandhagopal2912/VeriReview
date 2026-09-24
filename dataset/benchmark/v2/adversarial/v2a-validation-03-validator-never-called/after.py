def _check_limit(limit):
    if limit < 0:
        raise ValueError("limit must not be negative")


def set_limit(account, limit):
    account.limit = limit
