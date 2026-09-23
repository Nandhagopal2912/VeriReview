import logging

from accounts.db import DatabaseError, database

logger = logging.getLogger(__name__)


class ServiceError(Exception):
    pass


def create_account(data):
    account_id = database.insert("accounts", data)
    return account_id
