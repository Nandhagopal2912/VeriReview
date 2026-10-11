def read_workers(env, default=4):
    raw = env.get("WORKERS")
    if raw is None:
        return default
    return int(raw)
