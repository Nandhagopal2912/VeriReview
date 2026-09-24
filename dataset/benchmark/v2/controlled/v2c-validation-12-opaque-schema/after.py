from api import schemas


def import_payload(store, payload):
    schemas.check(payload)
    store.bulk_insert(payload["records"])
