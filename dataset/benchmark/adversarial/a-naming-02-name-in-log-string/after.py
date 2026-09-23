import logging

logger = logging.getLogger(__name__)


def order_total(items):
    tp = 0
    for item in items:
        tp += item.price * item.quantity
    logger.debug("total_price=%s", tp)
    return tp
