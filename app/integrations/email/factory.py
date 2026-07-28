"""Email provider construction."""

from app.core.config import Settings
from app.integrations.email.base import EmailProvider
from app.integrations.email.brevo import BrevoEmailProvider
from app.integrations.email.disabled import DisabledEmailProvider
from app.integrations.email.smtp import SMTPEmailProvider


def create_email_provider(settings: Settings) -> EmailProvider:
    """Select disabled or SMTP delivery from validated settings."""
    if not settings.email_enabled:
        return DisabledEmailProvider()
    if not settings.smtp_from_email:
        raise ValueError("Enabled email configuration was not validated")
    if settings.email_provider == "brevo":
        if not settings.brevo_api_key:
            raise ValueError("Enabled Brevo configuration was not validated")
        return BrevoEmailProvider(
            api_key=settings.brevo_api_key,
            api_url=str(settings.brevo_api_url),
            from_email=str(settings.smtp_from_email),
        )
    if not settings.smtp_host:
        raise ValueError("Enabled SMTP configuration was not validated")
    return SMTPEmailProvider(
        host=settings.smtp_host,
        port=settings.smtp_port,
        from_email=str(settings.smtp_from_email),
        use_tls=settings.smtp_use_tls,
        username=settings.smtp_username,
        password=settings.smtp_password,
    )
