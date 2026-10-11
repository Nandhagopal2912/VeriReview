def read_workers(env, default=4):
    raw = env.get("WORKERS")
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default
