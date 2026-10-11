import logging

logger = logging.getLogger(__name__)


def transfer(source, target, amount):
    logger.info("transfer of %s from %s to %s", amount, source.id, target.id)
    source.balance -= amount
    target.balance += amount
