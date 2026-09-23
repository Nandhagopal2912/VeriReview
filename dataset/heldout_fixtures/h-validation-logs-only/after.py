import logging

logger = logging.getLogger(__name__)


def blend(a, b, ratio):
    if ratio < 0 or ratio > 1:
        logger.warning("ratio out of range: %s", ratio)
    return a * ratio + b * (1 - ratio)
