import logging

import pytest
from sqlalchemy.ext.asyncio import create_async_engine

from app.db.base import Base
from app.db.models.contact_request import (
    ContactRequest,
    EmailStatus,
    ProcessingStatus,
)
from app.db.session import create_session_factory
from app.integrations.email.base import OutgoingEmail
from app.integrations.email.disabled import DisabledEmailProvider
from app.integrations.email.smtp import EmailDeliveryError, validate_header
from app.repositories.contact import ContactRequestRepository
from app.services.email import EmailService, process_contact_emails


class PartialFailureProvider:
    def __init__(self) -> None:
        self.calls = 0

    async def send(self, _message: OutgoingEmail) -> EmailStatus:
        self.calls += 1
        if self.calls == 2:
            raise EmailDeliveryError("simulated failure")
        return EmailStatus.SENT


async def test_disabled_provider_skips_without_logging_personal_data(
    caplog: pytest.LogCaptureFixture,
) -> None:
    private_value = "private@example.com"
    with caplog.at_level(logging.INFO):
        result = await DisabledEmailProvider().send(
            OutgoingEmail(
                recipient=private_value,
                subject="Private subject",
                body="Private body",
            )
        )

    assert result is EmailStatus.SKIPPED
    assert "email_delivery_skipped" in caplog.text
    assert private_value not in caplog.text
    assert "Private body" not in caplog.text


def test_email_header_injection_is_rejected() -> None:
    with pytest.raises(EmailDeliveryError, match="line break"):
        validate_header("owner@example.com\r\nBcc: attacker@example.com")


async def test_background_email_processing_persists_partial_failure() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session_factory = create_session_factory(engine)

    async with session_factory.begin() as session:
        contact = await ContactRequestRepository(session).create(
            name="Ada Lovelace",
            phone="+442079460123",
            email="ada@example.com",
            comment="I would like to discuss a backend project.",
            source_ip_hash=None,
            user_agent=None,
        )
        contact_id = contact.id

    service = EmailService(
        PartialFailureProvider(),
        owner_email="owner@example.com",
    )
    await process_contact_emails(contact_id, session_factory, service)

    async with session_factory() as session:
        stored = await session.get(ContactRequest, contact_id)

    assert stored is not None
    assert stored.owner_email_status is EmailStatus.SENT
    assert stored.user_email_status is EmailStatus.FAILED
    assert stored.processing_status is ProcessingStatus.PARTIAL
    await engine.dispose()
