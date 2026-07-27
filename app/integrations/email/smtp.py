"""SMTP email provider."""

import asyncio
import smtplib
from email.message import EmailMessage

from app.db.models.contact_request import EmailStatus
from app.integrations.email.base import OutgoingEmail


class EmailDeliveryError(Exception):
    """Safe SMTP delivery failure."""


def validate_header(value: str) -> str:
    """Reject CR/LF to prevent email header injection."""
    if "\r" in value or "\n" in value:
        raise EmailDeliveryError("Email header contains a line break")
    return value


class SMTPEmailProvider:
    """Deliver plain-text messages through a configured SMTP server."""

    def __init__(
        self,
        *,
        host: str,
        port: int,
        from_email: str,
        use_tls: bool,
        username: str | None,
        password: str | None,
        timeout_seconds: int = 10,
    ) -> None:
        self.host = host
        self.port = port
        self.from_email = validate_header(from_email)
        self.use_tls = use_tls
        self.username = username
        self.password = password
        self.timeout_seconds = timeout_seconds

    async def send(self, message: OutgoingEmail) -> EmailStatus:
        """Build a safe message and send it without blocking the event loop."""
        email_message = EmailMessage()
        email_message["From"] = self.from_email
        email_message["To"] = validate_header(message.recipient)
        email_message["Subject"] = validate_header(message.subject)
        email_message.set_content(message.body)
        try:
            await asyncio.to_thread(self._send_sync, email_message)
        except (OSError, smtplib.SMTPException) as error:
            raise EmailDeliveryError("SMTP delivery failed") from error
        return EmailStatus.SENT

    def _send_sync(self, message: EmailMessage) -> None:
        with smtplib.SMTP(
            self.host,
            self.port,
            timeout=self.timeout_seconds,
        ) as smtp:
            if self.use_tls:
                smtp.starttls()
            if self.username and self.password:
                smtp.login(self.username, self.password)
            smtp.send_message(message)
