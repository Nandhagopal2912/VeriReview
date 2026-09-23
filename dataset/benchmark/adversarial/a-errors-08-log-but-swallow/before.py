import logging

logger = logging.getLogger(__name__)


def upload(bucket, key, data):
    bucket.put(key, data)
