"""Contact request repository."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.contact_request import ContactRequest
from app.schemas.ai import AIClassification


class ContactRequestRepository:
    """Persist and retrieve contact requests within a caller-owned transaction."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        *,
        name: str,
        phone: str,
        email: str,
        comment: str,
        source_ip_hash: str | None,
        user_agent: str | None,
    ) -> ContactRequest:
        """Add a processing contact and make generated values available."""
        contact = ContactRequest(
            name=name,
            phone=phone,
            email=email,
            comment=comment,
            source_ip_hash=source_ip_hash,
            user_agent=user_agent,
        )
        self.session.add(contact)
        await self.session.flush()
        await self.session.refresh(contact)
        return contact

    async def get_by_id(self, contact_id: uuid.UUID) -> ContactRequest | None:
        """Return one contact request by primary key."""
        return await self.session.get(ContactRequest, contact_id)

    async def save_ai_classification(
        self,
        contact: ContactRequest,
        classification: AIClassification,
    ) -> None:
        """Apply a validated AI result to a tracked contact."""
        contact.category = classification.category
        contact.sentiment = classification.sentiment
        contact.urgency = classification.urgency
        contact.ai_summary = classification.summary
        contact.ai_provider_status = classification.provider_status
        await self.session.flush()
