from collections.abc import Iterator
from unittest.mock import MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from verireview import __version__
from verireview.db.session import get_session


def test_health_returns_ok_and_version(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": __version__}


def test_health_db_ok_when_query_succeeds(app: FastAPI, client: TestClient) -> None:
    session = MagicMock()

    def fake_session() -> Iterator[MagicMock]:
        yield session

    app.dependency_overrides[get_session] = fake_session
    response = client.get("/health/db")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    session.execute.assert_called_once()


def test_health_db_returns_503_without_leaking_error(app: FastAPI, client: TestClient) -> None:
    session = MagicMock()
    session.execute.side_effect = OperationalError(
        "SELECT 1", {}, Exception("password=hunter2 host=db")
    )

    def failing_session() -> Iterator[MagicMock]:
        yield session

    app.dependency_overrides[get_session] = failing_session
    response = client.get("/health/db")

    assert response.status_code == 503
    assert response.json() == {"detail": "database unavailable"}
    assert "hunter2" not in response.text
