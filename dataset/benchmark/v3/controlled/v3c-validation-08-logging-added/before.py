import logging

logger = logging.getLogger(__name__)


def transfer(source, target, amount):
    source.balance -= amount
    target.balance += amount
