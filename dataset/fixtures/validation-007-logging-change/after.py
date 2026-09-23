import json
import logging

logger = logging.getLogger(__name__)


def handle_webhook(payload):
    event = json.loads(payload)
    logger.info("received event %s", event.get("type"))
    return event["type"]
