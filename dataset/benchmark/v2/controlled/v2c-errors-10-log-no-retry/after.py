import logging

logger = logging.getLogger(__name__)


def push(remote, data):
    try:
        remote.send(data)
    except ConnectionError:
        logger.warning("push to %s failed", remote.url)
        raise
