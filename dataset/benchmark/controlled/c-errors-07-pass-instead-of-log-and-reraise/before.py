import logging

logger = logging.getLogger(__name__)


def push(remote, changes):
    remote.send(changes)
