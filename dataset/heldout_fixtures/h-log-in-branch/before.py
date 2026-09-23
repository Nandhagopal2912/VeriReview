import logging

logger = logging.getLogger(__name__)


def cached(cache, key, load):
    value = cache.get(key)
    if value is None:
        value = load(key)
    return value
