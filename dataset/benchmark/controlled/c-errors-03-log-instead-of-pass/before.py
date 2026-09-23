import logging

logger = logging.getLogger(__name__)


def cleanup(storage, keys):
    for key in keys:
        try:
            storage.delete(key)
        except Exception:
            pass
