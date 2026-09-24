"""Application settings, loaded from environment variables (prefix ``VERIREVIEW_``) and ``.env``."""

from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


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
    # Phase 12: categories to enforce (comma-separated), intersected with the shipped
    # eligibility (none today), and per-repository promotion rules.
    policy_enforced_categories: Annotated[list[str], NoDecode] = []
    enforcement_min_human_review_days: int = 14
    enforcement_min_confirmations: int = 10

    # Dashboard (Phase 13): off unless a token is set; the operator signs in with it.
    dashboard_token: SecretStr | None = None
    dashboard_session_hours: int = 8
    # Stored review cases (code, diff) are removed from audit rows after this many days.
    audit_retention_days: int = 90

    # GitHub App (Phase 11, advisory mode). The private key is PEM text, or a file path in
    # `github_app_private_key_path`; the webhook secret signs every delivery. None of them is
    # ever logged or stored in the database.
    github_app_id: int | None = None
    github_app_private_key: SecretStr | None = None
    github_app_private_key_path: Path | None = None
    github_webhook_secret: SecretStr | None = None
    advisory_check_name: str = "VeriReview"
    worker_poll_interval_s: float = 2.0
    worker_max_attempts: int = 3

    @field_validator(
        "github_token",
        "github_app_private_key",
        "github_webhook_secret",
        "dashboard_token",
        mode="before",
    )
    @classmethod
    def _blank_secret_is_none(cls, value: object) -> object:
        return None if isinstance(value, str) and not value.strip() else value

    @field_validator("policy_enforced_categories", mode="before")
    @classmethod
    def _comma_list(cls, value: object) -> object:
        if isinstance(value, str):
            return [v.strip() for v in value.split(",") if v.strip()]
        return value

    @field_validator("github_app_id", "github_app_private_key_path", mode="before")
    @classmethod
    def _blank_is_none(cls, value: object) -> object:
        return None if isinstance(value, str) and not value.strip() else value

    def app_private_key(self) -> SecretStr | None:
        """The App's PEM key: inline (``\\n`` escapes allowed, for .env files) or from a file."""
        if self.github_app_private_key is not None:
            pem = self.github_app_private_key.get_secret_value().replace("\\n", "\n")
            return SecretStr(pem)
        if self.github_app_private_key_path is not None:
            return SecretStr(self.github_app_private_key_path.read_text(encoding="utf-8"))
        return None

    @property
    def github_app_configured(self) -> bool:
        return self.github_app_id is not None and (
            self.github_app_private_key is not None or self.github_app_private_key_path is not None
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
