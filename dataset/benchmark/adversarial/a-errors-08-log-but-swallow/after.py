import logging

logger = logging.getLogger(__name__)


def upload(bucket, key, data):
    try:
        bucket.put(key, data)
    except OSError:
        logger.exception("upload of %s failed", key)
        return None
