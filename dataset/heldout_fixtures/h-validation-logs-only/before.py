import logging

logger = logging.getLogger(__name__)


def blend(a, b, ratio):
    return a * ratio + b * (1 - ratio)
