"""Contact request application service."""

from app.db.models.contact_request import ContactRequest
from app.integrations.ai.base import AIProvider
from app.repositories.contact import ContactRequestRepository
from app.schemas.contact import ContactCreate


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
