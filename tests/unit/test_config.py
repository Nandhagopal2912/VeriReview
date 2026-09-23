import pytest

from verireview.config import Settings


def test_settings_read_prefixed_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VERIREVIEW_ENVIRONMENT", "test")
    monkeypatch.setenv("VERIREVIEW_DATABASE_URL", "postgresql+psycopg://u:s3cret@h:5432/d")

    settings = Settings(_env_file=None)

    assert settings.environment == "test"
    assert settings.database_url.get_secret_value().endswith("@h:5432/d")


def test_database_url_is_masked_in_repr() -> None:
    settings = Settings(_env_file=None, database_url="postgresql+psycopg://u:s3cret@h/d")

    assert "s3cret" not in repr(settings)
