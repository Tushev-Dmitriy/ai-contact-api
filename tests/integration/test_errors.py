from collections.abc import AsyncIterator
from pathlib import Path
from typing import cast

from httpx import ASGITransport, AsyncClient
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.db.dependencies import get_session
from app.integrations.ai.base import AIProvider
from app.integrations.ai.fallback import FallbackAIProvider
from app.integrations.email.disabled import DisabledEmailProvider
from app.main import create_app
from app.services.dependencies import (
    get_ai_provider,
    get_email_service,
    get_rate_limiter,
)
from app.services.email import EmailService
from app.services.rate_limit import RateLimitResult, RedisRateLimiter


class AllowingRateLimiter:
    async def enforce(self, _identity_hash: str) -> RateLimitResult:
        return RateLimitResult(
            allowed=True,
            remaining=4,
            retry_after_seconds=900,
        )


def build_settings(tmp_path: Path) -> Settings:
    return Settings(
        app_env="test",
        app_log_file=tmp_path / "app.log",
        ip_hash_salt="integration-test-salt",
    )


async def test_database_error_returns_safe_503_contract(tmp_path: Path) -> None:
    application = create_app(build_settings(tmp_path))

    async def unavailable_session() -> AsyncIterator[AsyncSession]:
        raise OperationalError("private SQL statement", {}, Exception("private"))
        yield cast(AsyncSession, None)

    application.dependency_overrides[get_session] = unavailable_session
    application.dependency_overrides[get_rate_limiter] = lambda: cast(
        RedisRateLimiter,
        AllowingRateLimiter(),
    )
    application.dependency_overrides[get_ai_provider] = lambda: cast(
        AIProvider,
        FallbackAIProvider(),
    )
    application.dependency_overrides[get_email_service] = lambda: EmailService(
        DisabledEmailProvider(),
        owner_email="owner@example.com",
    )

    async with AsyncClient(
        transport=ASGITransport(app=application, raise_app_exceptions=False),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/api/contact",
            json={
                "name": "Ada Lovelace",
                "phone": "+442079460123",
                "email": "ada@example.com",
                "comment": "A sufficiently long contact comment.",
            },
        )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "database_unavailable"
    assert "private" not in response.text
    assert response.json()["error"]["request_id"] == response.headers["X-Request-ID"]


async def test_not_found_uses_error_envelope(tmp_path: Path) -> None:
    application = create_app(build_settings(tmp_path))

    async with AsyncClient(
        transport=ASGITransport(app=application),
        base_url="http://test",
    ) as client:
        response = await client.get("/missing")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"
    assert response.json()["error"]["request_id"] == response.headers["X-Request-ID"]


async def test_unknown_error_does_not_leak_exception(tmp_path: Path) -> None:
    application = create_app(build_settings(tmp_path))

    @application.get("/crash")
    async def crash() -> None:
        raise RuntimeError("private implementation detail")

    async with AsyncClient(
        transport=ASGITransport(app=application, raise_app_exceptions=False),
        base_url="http://test",
    ) as client:
        response = await client.get("/crash")

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "internal_error"
    assert "private implementation detail" not in response.text
    assert response.json()["error"]["request_id"] == response.headers["X-Request-ID"]
