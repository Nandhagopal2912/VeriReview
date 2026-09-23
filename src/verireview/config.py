"""Application settings, loaded from environment variables (prefix ``VERIREVIEW_``) and ``.env``."""

from functools import lru_cache
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="VERIREVIEW_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: Literal["development", "test", "production"] = "development"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    # SecretStr keeps the password out of reprs and logs.
    database_url: SecretStr = SecretStr(
        "postgresql+psycopg://verireview:verireview@localhost:5433/verireview"
    )
    database_connect_timeout_s: int = 5


@lru_cache
def get_settings() -> Settings:
    return Settings()
