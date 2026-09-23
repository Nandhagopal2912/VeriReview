import logging

logger = logging.getLogger(__name__)


def push(remote, changes):
    try:
        remote.send(changes)
    except ConnectionError:
        pass
