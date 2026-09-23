import logging

logger = logging.getLogger(__name__)


def cached(cache, key, load):
    value = cache.get(key)
    if value is None:
        logger.warning("cache miss for %s", key)
        value = load(key)
    return value
