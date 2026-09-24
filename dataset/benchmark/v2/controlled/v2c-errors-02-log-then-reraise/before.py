import logging

logger = logging.getLogger(__name__)


def pull(remote):
    try:
        return remote.fetch()
    except OSError:
        raise
