"""Safe disabled email provider."""

import logging

from app.db.models.contact_request import EmailStatus
from app.integrations.email.base import OutgoingEmail

logger = logging.getLogger(__name__)


class DisabledEmailProvider:
    """Skip delivery without logging recipient or message contents."""

    async def send(self, message: OutgoingEmail) -> EmailStatus:
        """Record only that disabled delivery was attempted."""
        del message
        logger.info("email_delivery_skipped", extra={"provider": "disabled"})
        return EmailStatus.SKIPPED
