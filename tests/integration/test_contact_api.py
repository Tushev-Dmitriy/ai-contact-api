from collections.abc import AsyncIterator
from pathlib import Path
from typing import cast

from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.config import Settings
from app.db.base import Base
from app.db.dependencies import get_session
from app.db.models.contact_request import (
    ContactCategory,
    ContactRequest,
    ProcessingStatus,
    ProviderStatus,
    Sentiment,
    Urgency,
)
from app.db.session import create_session_factory
from app.integrations.ai.base import AIProvider
from app.integrations.ai.fallback import FallbackAIProvider
from app.integrations.email.disabled import DisabledEmailProvider
from app.main import create_app
from app.schemas.ai import AIClassification
from app.services.dependencies import (
    get_ai_provider,
    get_email_service,
    get_rate_limiter,
)
from app.services.email import EmailService
from app.services.rate_limit import (
    RateLimitExceededError,
    RateLimitResult,
    RedisRateLimiter,
)


class AllowingRateLimiter:
    async def enforce(self, _identity_hash: str) -> RateLimitResult:
        return RateLimitResult(
            allowed=True,
            remaining=4,
            retry_after_seconds=900,
        )


class RejectingRateLimiter:
    async def enforce(self, _identity_hash: str) -> RateLimitResult:
        raise RateLimitExceededError(retry_after_seconds=123)


class StaticAIProvider:
    async def classify(self, _comment: str) -> AIClassification:
        return AIClassification(
            category=ContactCategory.JOB_OFFER,
            sentiment=Sentiment.POSITIVE,
            urgency=Urgency.MEDIUM,
            summary="A job opportunity.",
            provider_status=ProviderStatus.AVAILABLE,
        )


def disabled_email_service() -> EmailService:
    return EmailService(
        DisabledEmailProvider(),
        owner_email="owner@example.com",
    )


async def test_contact_endpoint_persists_normalized_request(tmp_path: Path) -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session_factory = create_session_factory(engine)

    async def override_session() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    settings = Settings(
        app_env="test",
        app_log_file=tmp_path / "app.log",
        ip_hash_salt="integration-test-salt",
    )
    application = create_app(settings)
    application.state.session_factory = session_factory
    application.dependency_overrides[get_session] = override_session
    application.dependency_overrides[get_rate_limiter] = lambda: cast(
        RedisRateLimiter,
        AllowingRateLimiter(),
    )
    application.dependency_overrides[get_ai_provider] = lambda: cast(
        AIProvider,
        StaticAIProvider(),
    )
    application.dependency_overrides[get_email_service] = disabled_email_service

    async with AsyncClient(
        transport=ASGITransport(app=application),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/api/v1/contact",
            headers={"user-agent": "integration-test"},
            json={
                "name": "  Ada   Lovelace ",
                "phone": " +44 (20) 7946-0123 ",
                "email": " ADA@Example.COM ",
                "comment": "  I would like to discuss a backend project.  ",
            },
        )

    assert response.status_code == 202
    assert response.json()["status"] == "accepted"
    assert response.json()["category"] == "job_offer"

    async with session_factory() as session:
        stored = (await session.scalars(select(ContactRequest))).one()

    assert str(stored.id) == response.json()["request_id"]
    assert stored.name == "Ada Lovelace"
    assert stored.phone == "+442079460123"
    assert stored.email == "ada@example.com"
    assert stored.processing_status is ProcessingStatus.COMPLETED
    assert stored.category is ContactCategory.JOB_OFFER
    assert stored.ai_provider_status is ProviderStatus.AVAILABLE
    assert stored.ai_summary == "A job opportunity."
    assert stored.source_ip_hash is not None
    assert stored.user_agent == "integration-test"
    await engine.dispose()


async def test_contact_endpoint_returns_validation_error(tmp_path: Path) -> None:
    settings = Settings(
        app_env="test",
        app_log_file=tmp_path / "app.log",
        ip_hash_salt="integration-test-salt",
    )
    application = create_app(settings)

    async def unused_session() -> AsyncIterator[AsyncSession]:
        yield cast(AsyncSession, None)

    application.dependency_overrides[get_session] = unused_session
    application.dependency_overrides[get_rate_limiter] = lambda: cast(
        RedisRateLimiter,
        AllowingRateLimiter(),
    )
    application.dependency_overrides[get_ai_provider] = lambda: cast(
        AIProvider,
        StaticAIProvider(),
    )
    application.dependency_overrides[get_email_service] = disabled_email_service

    async with AsyncClient(
        transport=ASGITransport(app=application),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/api/v1/contact",
            json={
                "name": "A",
                "phone": "123",
                "email": "invalid",
                "comment": "short",
            },
        )

    assert response.status_code == 422
    assert response.headers["X-Request-ID"]


async def test_contact_endpoint_returns_429_when_rate_limit_is_exceeded(
    tmp_path: Path,
) -> None:
    settings = Settings(
        app_env="test",
        app_log_file=tmp_path / "app.log",
        ip_hash_salt="integration-test-salt",
    )
    application = create_app(settings)

    async def unused_session() -> AsyncIterator[AsyncSession]:
        yield cast(AsyncSession, None)

    application.dependency_overrides[get_session] = unused_session
    application.dependency_overrides[get_rate_limiter] = lambda: cast(
        RedisRateLimiter,
        RejectingRateLimiter(),
    )
    application.dependency_overrides[get_ai_provider] = lambda: cast(
        AIProvider,
        StaticAIProvider(),
    )
    application.dependency_overrides[get_email_service] = disabled_email_service

    async with AsyncClient(
        transport=ASGITransport(app=application),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/api/v1/contact",
            json={
                "name": "Ada Lovelace",
                "phone": "+442079460123",
                "email": "ada@example.com",
                "comment": "A sufficiently long contact comment.",
            },
        )

    assert response.status_code == 429
    assert response.headers["Retry-After"] == "123"


async def test_contact_is_accepted_when_ai_uses_fallback(tmp_path: Path) -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session_factory = create_session_factory(engine)

    async def override_session() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    settings = Settings(
        app_env="test",
        app_log_file=tmp_path / "app.log",
        ip_hash_salt="integration-test-salt",
    )
    application = create_app(settings)
    application.state.session_factory = session_factory
    application.dependency_overrides[get_session] = override_session
    application.dependency_overrides[get_rate_limiter] = lambda: cast(
        RedisRateLimiter,
        AllowingRateLimiter(),
    )
    application.dependency_overrides[get_ai_provider] = FallbackAIProvider
    application.dependency_overrides[get_email_service] = disabled_email_service

    async with AsyncClient(
        transport=ASGITransport(app=application),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/api/v1/contact",
            json={
                "name": "Ada Lovelace",
                "phone": "+442079460123",
                "email": "ada@example.com",
                "comment": "I would like to discuss a backend project.",
            },
        )

    assert response.status_code == 202
    assert response.json()["category"] == "other"
    async with session_factory() as session:
        stored = (await session.scalars(select(ContactRequest))).one()
    assert stored.ai_provider_status is ProviderStatus.UNAVAILABLE
    assert stored.category is ContactCategory.OTHER
    await engine.dispose()
