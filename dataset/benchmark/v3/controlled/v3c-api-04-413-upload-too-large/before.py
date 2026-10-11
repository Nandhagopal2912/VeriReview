MAX_BYTES = 5_000_000
STORE = {}


def handle_upload(name, data):
    STORE[name] = data
    return {"stored": name}, 200
