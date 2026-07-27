"""Email message creation and background delivery."""

import logging
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models.contact_request import (
    ContactRequest,
    EmailStatus,
    ProcessingStatus,
)
from app.integrations.email.base import EmailProvider, OutgoingEmail
from app.repositories.contact import ContactRequestRepository

logger = logging.getLogger(__name__)


class EmailService:
    """Build required plain-text messages and delegate their delivery."""

    def __init__(self, provider: EmailProvider, *, owner_email: str) -> None:
        self.provider = provider
        self.owner_email = owner_email

    async def send_owner_notification(
        self,
        contact: ContactRequest,
    ) -> EmailStatus:
        """Send the site owner all fields required by the assignment."""
        category = contact.category.value if contact.category else "other"
        sentiment = contact.sentiment.value if contact.sentiment else "neutral"
        urgency = contact.urgency.value if contact.urgency else "low"
        created_at = contact.created_at.astimezone(UTC).isoformat()
        body = "\n".join(
            [
                f"Request ID: {contact.id}",
                f"Name: {contact.name}",
                f"Phone: {contact.phone}",
                f"Email: {contact.email}",
                f"Comment: {contact.comment}",
                f"AI category: {category}",
                f"Sentiment: {sentiment}",
                f"Urgency: {urgency}",
                f"Created at: {created_at}",
            ]
        )
        return await self.provider.send(
            OutgoingEmail(
                recipient=self.owner_email,
                subject="New portfolio contact request",
                body=body,
            )
        )

    async def send_user_confirmation(
        self,
        contact: ContactRequest,
    ) -> EmailStatus:
        """Send a neutral confirmation that does not promise a response time."""
        body = "\n".join(
            [
                f"Hello, {contact.name}.",
                "",
                "Thank you for your message. It has been received.",
                "The site owner will review it and respond when possible.",
                "",
                f"Request ID: {contact.id}",
            ]
        )
        return await self.provider.send(
            OutgoingEmail(
                recipient=contact.email,
                subject="Your message has been received",
                body=body,
            )
        )


async def process_contact_emails(
    contact_id: uuid.UUID,
    session_factory: async_sessionmaker[AsyncSession],
    email_service: EmailService,
) -> None:
    """Deliver both emails and persist independent outcomes."""
    async with session_factory() as session:
        repository = ContactRequestRepository(session)
        contact = await repository.get_by_id(contact_id)
        if contact is None:
            logger.error("email_contact_not_found")
            return

        contact.owner_email_status = await _deliver_safely(
            email_service.send_owner_notification,
            contact,
            kind="owner",
        )
        contact.user_email_status = await _deliver_safely(
            email_service.send_user_confirmation,
            contact,
            kind="user",
        )
        successful_statuses = {EmailStatus.SENT, EmailStatus.SKIPPED}
        if {
            contact.owner_email_status,
            contact.user_email_status,
        }.issubset(successful_statuses):
            contact.processing_status = ProcessingStatus.COMPLETED
        else:
            contact.processing_status = ProcessingStatus.PARTIAL
        await session.commit()


async def _deliver_safely(
    send_email: Callable[[ContactRequest], Awaitable[EmailStatus]],
    contact: ContactRequest,
    *,
    kind: str,
) -> EmailStatus:
    try:
        return await send_email(contact)
    except Exception as error:
        logger.error(
            "email_delivery_failed",
            extra={"kind": kind, "error_type": type(error).__name__},
        )
        return EmailStatus.FAILED
