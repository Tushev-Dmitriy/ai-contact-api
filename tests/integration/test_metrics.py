from collections.abc import AsyncIterator
from pathlib import Path

from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.config import Settings
from app.db.base import Base
from app.db.dependencies import get_session
from app.db.models.contact_request import (
    ContactCategory,
    ContactRequest,
    EmailStatus,
    ProviderStatus,
    Sentiment,
)
from app.db.session import create_session_factory
from app.main import create_app
from app.repositories.metrics import MetricsRepository


async def seed_metrics(session: AsyncSession) -> None:
    session.add_all(
        [
            ContactRequest(
                name="First",
                phone="+12025550101",
                email="first@example.com",
                comment="First sufficiently long comment.",
                category=ContactCategory.JOB_OFFER,
                sentiment=Sentiment.POSITIVE,
                ai_provider_status=ProviderStatus.AVAILABLE,
                owner_email_status=EmailStatus.SENT,
                user_email_status=EmailStatus.FAILED,
            ),
            ContactRequest(
                name="Second",
                phone="+12025550102",
                email="second@example.com",
                comment="Second sufficiently long comment.",
                category=ContactCategory.JOB_OFFER,
                sentiment=Sentiment.NEUTRAL,
                ai_provider_status=ProviderStatus.UNAVAILABLE,
                owner_email_status=EmailStatus.FAILED,
                user_email_status=EmailStatus.SKIPPED,
            ),
        ]
    )
    await session.commit()


async def test_metrics_repository_returns_required_aggregates() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session_factory = create_session_factory(engine)
    async with session_factory() as session:
        await seed_metrics(session)
        metrics = await MetricsRepository(session).get_contact_metrics()

    assert metrics.total_requests == 2
    assert metrics.requests_today == 2
    assert metrics.categories == {"job_offer": 2}
    assert metrics.sentiment == {"neutral": 1, "positive": 1}
    assert metrics.email_failures == 2
    assert metrics.ai_fallback_count == 1
    await engine.dispose()


async def test_metrics_endpoint_is_hidden_without_key(tmp_path: Path) -> None:
    settings = Settings(
        app_env="test",
        app_log_file=tmp_path / "app.log",
        ip_hash_salt="integration-test-salt",
    )
    application = create_app(settings)

    async with AsyncClient(
        transport=ASGITransport(app=application),
        base_url="http://test",
    ) as client:
        response = await client.get("/api/v1/metrics")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


async def test_metrics_endpoint_requires_valid_key_and_returns_data(
    tmp_path: Path,
) -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session_factory = create_session_factory(engine)
    async with session_factory() as session:
        await seed_metrics(session)

    async def override_session() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    settings = Settings(
        app_env="test",
        app_log_file=tmp_path / "app.log",
        ip_hash_salt="integration-test-salt",
        metrics_api_key="metrics-secret",
    )
    application = create_app(settings)
    application.dependency_overrides[get_session] = override_session

    async with AsyncClient(
        transport=ASGITransport(app=application),
        base_url="http://test",
    ) as client:
        denied = await client.get(
            "/api/v1/metrics",
            headers={"X-API-Key": "wrong"},
        )
        allowed = await client.get(
            "/api/v1/metrics",
            headers={"X-API-Key": "metrics-secret"},
        )

    assert denied.status_code == 404
    assert allowed.status_code == 200
    assert allowed.json()["total_requests"] == 2
    assert "example.com" not in allowed.text
    assert "first@" not in allowed.text
    await engine.dispose()
