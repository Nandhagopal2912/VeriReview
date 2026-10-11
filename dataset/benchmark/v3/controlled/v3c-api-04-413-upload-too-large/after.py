MAX_BYTES = 5_000_000
STORE = {}


def handle_upload(name, data):
    if len(data) > MAX_BYTES:
        return {"error": "upload too large"}, 413
    STORE[name] = data
    return {"stored": name}, 200
