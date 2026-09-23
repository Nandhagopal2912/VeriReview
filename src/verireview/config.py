"""Application settings, loaded from environment variables (prefix ``VERIREVIEW_``) and ``.env``."""

from functools import lru_cache
from typing import Literal

from pydantic import SecretStr, field_validator
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

    # GitHub. Without a token, only public REST data is available (60 requests/hour) and
    # thread resolution state is unknown, because GraphQL requires authentication.
    github_token: SecretStr | None = None
    github_api_url: str = "https://api.github.com"
    github_timeout_s: float = 30.0
    github_max_retries: int = 3

    # Policy (plan §27). Blocking stays off until Phase 12's evaluation; see policy/decision.py.
    policy_mode: Literal["observe", "advisory", "human_review", "enforcement"] = "advisory"
    policy_allow_block: bool = False

    @field_validator("github_token", mode="before")
    @classmethod
    def _blank_token_is_none(cls, value: object) -> object:
        return None if isinstance(value, str) and not value.strip() else value


@lru_cache
def get_settings() -> Settings:
    return Settings()
