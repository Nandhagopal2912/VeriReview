def set_limit(account, limit):
    account.limit = limit


def set_limit_checked(account, limit):
    if limit < 0:
        raise ValueError("limit must not be negative")
    account.limit = limit
