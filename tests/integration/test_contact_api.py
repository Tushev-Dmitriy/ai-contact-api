from collections.abc import AsyncIterator
from pathlib import Path
from typing import cast

from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.config import Settings
from app.db.base import Base
from app.db.dependencies import get_session
from app.db.models.contact_request import ContactRequest, ProcessingStatus
from app.db.session import create_session_factory
from app.main import create_app


async def test_contact_endpoint_persists_normalized_request(tmp_path: Path) -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session_factory = create_session_factory(engine)

    async def override_session() -> AsyncIterator[AsyncSession]:
        async with session_factory.begin() as session:
            yield session

    settings = Settings(
        app_env="test",
        app_log_file=tmp_path / "app.log",
        ip_hash_salt="integration-test-salt",
    )
    application = create_app(settings)
    application.dependency_overrides[get_session] = override_session

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
    assert "category" not in response.json()

    async with session_factory() as session:
        stored = (await session.scalars(select(ContactRequest))).one()

    assert str(stored.id) == response.json()["request_id"]
    assert stored.name == "Ada Lovelace"
    assert stored.phone == "+442079460123"
    assert stored.email == "ada@example.com"
    assert stored.processing_status is ProcessingStatus.PROCESSING
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
