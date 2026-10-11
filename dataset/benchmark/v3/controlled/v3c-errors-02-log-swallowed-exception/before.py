import logging

logger = logging.getLogger(__name__)


def run_sync(client):
    try:
        client.pull()
        client.push()
    except Exception:
        pass
