import logging

from payments.gateway import GatewayError, gateway

logger = logging.getLogger(__name__)


def charge(customer_id, amount):
    try:
        return gateway.charge(customer_id, amount)
    except GatewayError:
        logger.exception("charge failed for customer %s", customer_id)
        raise
