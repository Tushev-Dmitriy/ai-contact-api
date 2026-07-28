"""Contact request application service."""

import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models.contact_request import ContactRequest
from app.integrations.ai.base import AIProvider
from app.repositories.contact import ContactRequestRepository
from app.schemas.contact import ContactCreate
from app.services.email import EmailService, process_contact_emails

logger = logging.getLogger(__name__)


class ContactService:
    """Coordinate persistence for a validated contact request."""

    def __init__(
        self,
        repository: ContactRequestRepository,
        ai_provider: AIProvider,
    ) -> None:
        self.repository = repository
        self.ai_provider = ai_provider

    async def create(
        self,
        contact: ContactCreate,
        *,
        source_ip_hash: str | None,
        user_agent: str | None,
    ) -> ContactRequest:
        """Persist a contact in the initial processing state."""
        return await self.repository.create(
            name=contact.name,
            phone=contact.phone,
            email=str(contact.email),
            comment=contact.comment,
            source_ip_hash=source_ip_hash,
            user_agent=user_agent[:512] if user_agent else None,
        )

    async def classify(
        self,
        stored_contact: ContactRequest,
        comment: str,
    ) -> None:
        """Classify a stored contact and persist the safe result."""
        classification = await self.ai_provider.classify(comment)
        await self.repository.save_ai_classification(
            stored_contact,
            classification,
        )


async def process_contact(
    contact_id: uuid.UUID,
    session_factory: async_sessionmaker[AsyncSession],
    ai_provider: AIProvider,
    email_service: EmailService,
) -> None:
    """Classify a persisted contact, then deliver and record both emails."""
    async with session_factory() as session:
        repository = ContactRequestRepository(session)
        contact = await repository.get_by_id(contact_id)
        if contact is None:
            logger.error("processing_contact_not_found")
            return
        service = ContactService(repository, ai_provider)
        await service.classify(contact, contact.comment)
        await session.commit()

    await process_contact_emails(contact_id, session_factory, email_service)
