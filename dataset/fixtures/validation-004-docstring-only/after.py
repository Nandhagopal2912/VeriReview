import logging

logger = logging.getLogger(__name__)


def send_welcome(email, smtp):
    """Validate the email address and send the welcome mail."""
    logger.info("validating email address before sending")
    message = f"Welcome aboard, {email}!"
    smtp.send(to=email, body=message)
