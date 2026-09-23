import logging

logger = logging.getLogger(__name__)


def send_welcome(email, smtp):
    message = f"Welcome aboard, {email}!"
    smtp.send(to=email, body=message)
