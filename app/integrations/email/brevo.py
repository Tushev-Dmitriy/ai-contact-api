"""Brevo transactional email provider using its HTTPS API."""

import httpx

from app.db.models.contact_request import EmailStatus
from app.integrations.email.base import OutgoingEmail
from app.integrations.email.smtp import EmailDeliveryError, validate_header


class BrevoEmailProvider:
    """Deliver plain-text messages without relying on blocked SMTP ports."""

    def __init__(
        self,
        *,
        api_key: str,
        api_url: str,
        from_email: str,
        timeout_seconds: int = 10,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.api_key = api_key
        self.api_url = api_url
        self.from_email = validate_header(from_email)
        self.timeout_seconds = timeout_seconds
        self.transport = transport

    async def send(self, message: OutgoingEmail) -> EmailStatus:
        """Send one transactional email and expose only a safe failure."""
        payload = {
            "sender": {"email": self.from_email},
            "to": [{"email": validate_header(message.recipient)}],
            "subject": validate_header(message.subject),
            "textContent": message.body,
        }
        headers = {
            "accept": "application/json",
            "api-key": self.api_key,
            "content-type": "application/json",
        }
        try:
            async with httpx.AsyncClient(
                timeout=self.timeout_seconds,
                transport=self.transport,
            ) as client:
                response = await client.post(
                    self.api_url,
                    headers=headers,
                    json=payload,
                )
                response.raise_for_status()
        except (httpx.HTTPError, OSError) as error:
            raise EmailDeliveryError("Brevo delivery failed") from error
        return EmailStatus.SENT
