def merge(defaults, overrides):
    result = dict(defaults)
    result.update(overrides or {})
    return result
