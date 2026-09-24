from api import schemas


def import_payload(store, payload):
    store.bulk_insert(payload["records"])
