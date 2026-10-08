"""Integration tests run against their own database, never the one the running system uses.

Found in the first live run: the tests shared the configured database with the live advisory
worker, which then claimed a test job, failed on it against real GitHub, and crashed when the
test cleaned the row up. Here the configured URL's database name gets a ``_test`` suffix; the
database is created if missing and migrated to head before any integration test runs.
"""

import os
from collections.abc import Iterator

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from verireview.config import get_settings
from verireview.db.session import get_engine, get_sessionmaker

SUFFIX = "_test"


def _clear_caches() -> None:
    get_settings.cache_clear()
    get_engine.cache_clear()
    get_sessionmaker.cache_clear()


@pytest.fixture(scope="session", autouse=True)
def separate_test_database() -> Iterator[None]:
    url = make_url(get_settings().database_url.get_secret_value())
    name = url.database or "verireview"
    test_url = url.set(database=name if name.endswith(SUFFIX) else name + SUFFIX)

    server = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with server.connect() as conn:
        exists = conn.execute(
            text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": test_url.database}
        ).scalar()
        if not exists:
            conn.execute(text(f'CREATE DATABASE "{test_url.database}"'))
    server.dispose()

    previous = os.environ.get("VERIREVIEW_DATABASE_URL")
    os.environ["VERIREVIEW_DATABASE_URL"] = test_url.render_as_string(hide_password=False)
    _clear_caches()
    command.upgrade(Config("alembic.ini"), "head")
    try:
        yield
    finally:
        get_engine().dispose()
        if previous is None:
            os.environ.pop("VERIREVIEW_DATABASE_URL", None)
        else:
            os.environ["VERIREVIEW_DATABASE_URL"] = previous
        _clear_caches()
