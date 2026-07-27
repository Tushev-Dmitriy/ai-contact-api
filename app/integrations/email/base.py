"""Email provider contract and message value object."""

from dataclasses import dataclass
from typing import Protocol

from app.db.models.contact_request import EmailStatus


@dataclass(frozen=True, slots=True)
class OutgoingEmail:
    """Plain-text email ready for provider delivery."""

    recipient: str
    subject: str
    body: str


class EmailProvider(Protocol):
    """Replaceable email delivery provider."""

    async def send(self, message: OutgoingEmail) -> EmailStatus:
        """Deliver or safely skip one message."""
        ...
