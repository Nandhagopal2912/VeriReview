"""Requires a running PostgreSQL (docker compose up -d db). Run: uv run pytest -m integration"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from verireview.db.session import get_engine

pytestmark = pytest.mark.integration


def test_database_accepts_queries() -> None:
    with get_engine().connect() as connection:
        assert connection.execute(text("SELECT 1")).scalar_one() == 1


def test_health_db_endpoint_against_real_database(client: TestClient) -> None:
    response = client.get("/health/db")

    assert response.status_code == 200
