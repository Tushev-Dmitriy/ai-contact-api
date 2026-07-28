from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core.config import (
    DEVELOPMENT_DATABASE_URL,
    DEVELOPMENT_IP_HASH_SALT,
    Settings,
)


def test_development_defaults_are_safe_to_start(tmp_path: Path) -> None:
    settings = Settings(app_env="test", app_log_file=tmp_path / "app.log")

    assert settings.ai_enabled is False
    assert settings.email_enabled is False
    assert settings.rate_limit_requests == 5
    assert settings.rate_limit_window_seconds == 900
    assert settings.cors_origins == [
        "http://localhost:3000",
        "http://localhost:5173",
    ]


def test_platform_postgres_url_is_normalized_for_asyncpg() -> None:
    settings = Settings(
        app_env="test",
        database_url="postgresql://user:password@postgres/database",
    )

    assert settings.database_url == (
        "postgresql+asyncpg://user:password@postgres/database"
    )


def test_ai_configuration_is_required_only_when_enabled() -> None:
    with pytest.raises(ValidationError, match="AI_API_KEY and AI_MODEL"):
        Settings(app_env="test", ai_enabled=True)


def test_email_configuration_is_required_only_when_enabled() -> None:
    with pytest.raises(ValidationError, match="SMTP_HOST"):
        Settings(app_env="test", email_enabled=True)


def test_smtp_credentials_must_be_configured_as_a_pair() -> None:
    with pytest.raises(ValidationError, match="configured together"):
        Settings(app_env="test", smtp_username="user")


def test_empty_optional_environment_values_are_disabled() -> None:
    settings = Settings(
        app_env="test",
        ai_api_key="",
        ai_model=" ",
        smtp_from_email="",
        smtp_owner_email=" ",
        metrics_api_key="",
    )

    assert settings.ai_api_key is None
    assert settings.ai_model is None
    assert settings.smtp_from_email is None
    assert settings.smtp_owner_email is None
    assert settings.metrics_api_key is None


def test_production_rejects_development_ip_hash_salt() -> None:
    with pytest.raises(ValidationError, match="IP_HASH_SALT"):
        Settings(
            app_env="production",
            database_url="postgresql+asyncpg://service@db/contact",
            ip_hash_salt=DEVELOPMENT_IP_HASH_SALT,
        )


def test_production_rejects_development_database_url() -> None:
    with pytest.raises(ValidationError, match="DATABASE_URL"):
        Settings(
            app_env="production",
            database_url=DEVELOPMENT_DATABASE_URL,
            ip_hash_salt="x" * 32,
        )


def test_database_url_requires_asyncpg_driver() -> None:
    with pytest.raises(ValidationError, match="postgresql\\+asyncpg"):
        Settings(app_env="test", database_url="sqlite:///test.db")


def test_production_accepts_explicit_database_and_long_ip_hash_salt() -> None:
    settings = Settings(
        app_env="production",
        database_url="postgresql+asyncpg://service@db/contact",
        ip_hash_salt="x" * 32,
    )

    assert settings.app_env == "production"
