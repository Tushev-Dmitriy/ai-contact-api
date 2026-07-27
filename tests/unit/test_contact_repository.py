from sqlalchemy.ext.asyncio import create_async_engine

from app.db.base import Base
from app.db.models.contact_request import (
    ContactRequest,
    EmailStatus,
    ProcessingStatus,
    ProviderStatus,
)
from app.db.session import create_session_factory
from app.repositories.contact import ContactRequestRepository


async def test_repository_creates_and_retrieves_processing_contact() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    session_factory = create_session_factory(engine)
    async with session_factory.begin() as session:
        repository = ContactRequestRepository(session)
        contact = await repository.create(
            name="Ada Lovelace",
            phone="+442079460123",
            email="ada@example.com",
            comment="I would like to discuss a backend project.",
            source_ip_hash="a" * 64,
            user_agent="pytest",
        )
        contact_id = contact.id

        assert contact.processing_status is ProcessingStatus.PROCESSING
        assert contact.ai_provider_status is ProviderStatus.PENDING
        assert contact.owner_email_status is EmailStatus.PENDING
        assert contact.user_email_status is EmailStatus.PENDING
        assert contact.created_at is not None

    async with session_factory() as session:
        stored = await ContactRequestRepository(session).get_by_id(contact_id)

    assert isinstance(stored, ContactRequest)
    assert stored.email == "ada@example.com"
    assert stored.source_ip_hash == "a" * 64
    await engine.dispose()
