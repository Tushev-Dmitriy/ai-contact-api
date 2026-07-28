"""Centralized application settings."""

from functools import lru_cache
from pathlib import Path
from typing import Literal, Self

from pydantic import (
    AnyHttpUrl,
    EmailStr,
    Field,
    PositiveInt,
    field_validator,
    model_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict

DEVELOPMENT_IP_HASH_SALT = "development-only-change-me"
DEVELOPMENT_DATABASE_URL = (
    "postgresql+asyncpg://postgres:postgres@localhost:5432/ai_contact"
)


class Settings(BaseSettings):
    """Application settings loaded from environment variables and `.env`."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_env: Literal["development", "test", "production"] = "development"
    app_host: str = "0.0.0.0"
    app_port: int = Field(default=8000, ge=1, le=65535)
    app_log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    app_log_file: Path = Path("logs/app.log")
    request_body_max_bytes: PositiveInt = 16_384
    ip_hash_salt: str = DEVELOPMENT_IP_HASH_SALT
    trust_proxy_headers: bool = False
    cors_allowed_origins: list[AnyHttpUrl] = [
        AnyHttpUrl("http://localhost:3000"),
        AnyHttpUrl("http://localhost:5173"),
    ]

    database_url: str = DEVELOPMENT_DATABASE_URL
    redis_url: str = "redis://localhost:6379/0"
    rate_limit_requests: PositiveInt = 5
    rate_limit_window_seconds: PositiveInt = 900

    ai_enabled: bool = False
    ai_api_key: str | None = None
    ai_base_url: AnyHttpUrl = AnyHttpUrl("https://api.openai.com/v1")
    ai_model: str | None = None
    ai_timeout_seconds: PositiveInt = 10

    email_enabled: bool = False
    email_provider: Literal["smtp"] = "smtp"
    smtp_host: str | None = None
    smtp_port: int = Field(default=587, ge=1, le=65535)
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_from_email: EmailStr | None = None
    smtp_owner_email: EmailStr | None = None
    smtp_use_tls: bool = True
    metrics_api_key: str | None = None

    @field_validator(
        "ai_api_key",
        "ai_model",
        "smtp_host",
        "smtp_username",
        "smtp_password",
        "smtp_from_email",
        "smtp_owner_email",
        "metrics_api_key",
        mode="before",
    )
    @classmethod
    def empty_optional_values_are_none(cls, value: object) -> object:
        """Treat empty Compose/environment values as disabled configuration."""
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("database_url", mode="before")
    @classmethod
    def normalize_postgres_driver(cls, value: object) -> object:
        """Adapt platform-provided PostgreSQL URLs to the asyncpg driver."""
        if isinstance(value, str) and value.startswith("postgresql://"):
            return value.replace("postgresql://", "postgresql+asyncpg://", 1)
        return value

    @model_validator(mode="after")
    def validate_environment(self) -> Self:
        """Reject unsafe or incomplete enabled configurations."""
        if not self.database_url.startswith("postgresql+asyncpg://"):
            raise ValueError("DATABASE_URL must use the postgresql+asyncpg driver")

        if self.ai_enabled and (not self.ai_api_key or not self.ai_model):
            raise ValueError("AI_API_KEY and AI_MODEL are required when AI is enabled")

        if self.email_enabled and self.email_provider == "smtp" and not self.smtp_host:
            raise ValueError("SMTP_HOST is required for the SMTP email provider")
        common_email_required = (self.smtp_from_email, self.smtp_owner_email)
        if self.email_enabled and not all(common_email_required):
            raise ValueError(
                "SMTP_FROM_EMAIL and SMTP_OWNER_EMAIL are required "
                "when email is enabled"
            )
        if self.email_provider == "smtp" and bool(self.smtp_username) != bool(
            self.smtp_password
        ):
            raise ValueError(
                "SMTP_USERNAME and SMTP_PASSWORD must be configured together"
            )

        if self.app_env == "production":
            if self.database_url == DEVELOPMENT_DATABASE_URL:
                raise ValueError("DATABASE_URL must be changed in production")
            if self.ip_hash_salt == DEVELOPMENT_IP_HASH_SALT:
                raise ValueError("IP_HASH_SALT must be changed in production")
            if len(self.ip_hash_salt) < 32:
                raise ValueError("IP_HASH_SALT must contain at least 32 characters")

        return self

    @property
    def cors_origins(self) -> list[str]:
        """Return origins in the format expected by Starlette."""
        return [str(origin).rstrip("/") for origin in self.cors_allowed_origins]


@lru_cache
def get_settings() -> Settings:
    """Return one immutable-by-convention settings instance per process."""
    return Settings()
