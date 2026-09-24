def set_limit(account, limit):
    if limit >= 0:
        raise ValueError("limit must not be negative")
    account.limit = limit
