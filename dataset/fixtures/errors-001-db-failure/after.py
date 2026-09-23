import logging

from accounts.db import DatabaseError, database

logger = logging.getLogger(__name__)


class ServiceError(Exception):
    pass


def create_account(data):
    try:
        account_id = database.insert("accounts", data)
    except DatabaseError as exc:
        logger.exception("could not insert account")
        raise ServiceError("could not create account") from exc
    return account_id
