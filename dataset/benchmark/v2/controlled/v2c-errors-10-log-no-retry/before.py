import logging

logger = logging.getLogger(__name__)


def push(remote, data):
    remote.send(data)
