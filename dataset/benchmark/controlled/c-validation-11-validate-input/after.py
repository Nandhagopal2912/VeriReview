def route(origin, destination, mode):
    if mode not in {"car", "bike", "walk"}:
        raise ValueError(f"unknown mode {mode!r}")
    return {"from": origin, "to": destination, "mode": mode}
