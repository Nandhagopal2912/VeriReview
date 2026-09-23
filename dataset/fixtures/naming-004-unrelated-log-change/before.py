import logging

logger = logging.getLogger(__name__)


def run_with_retries(task, x=3):
    for attempt in range(x):
        try:
            return task()
        except ConnectionError:
            logger.warning("attempt failed")
    raise RuntimeError("all attempts failed")
