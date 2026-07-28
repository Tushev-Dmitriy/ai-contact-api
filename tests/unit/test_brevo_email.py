import json

import httpx
import pytest

from app.db.models.contact_request import EmailStatus
from app.integrations.email.base import OutgoingEmail
from app.integrations.email.brevo import BrevoEmailProvider
from app.integrations.email.smtp import EmailDeliveryError


async def test_brevo_provider_sends_plain_text_payload() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["api-key"] == "secret"
        payload = json.loads(request.content)
        assert payload["sender"]["email"] == "sender@example.com"
        assert payload["to"] == [{"email": "user@example.com"}]
        assert payload["textContent"] == "Plain text body"
        return httpx.Response(201, json={"messageId": "example"})

    provider = BrevoEmailProvider(
        api_key="secret",
        api_url="https://api.brevo.test/v3/smtp/email",
        from_email="sender@example.com",
        transport=httpx.MockTransport(handler),
    )

    result = await provider.send(
        OutgoingEmail(
            recipient="user@example.com",
            subject="Subject",
            body="Plain text body",
        )
    )

    assert result is EmailStatus.SENT


async def test_brevo_provider_raises_safe_error() -> None:
    transport = httpx.MockTransport(
        lambda _request: httpx.Response(401, json={"message": "private details"})
    )
    provider = BrevoEmailProvider(
        api_key="secret",
        api_url="https://api.brevo.test/v3/smtp/email",
        from_email="sender@example.com",
        transport=transport,
    )

    with pytest.raises(EmailDeliveryError, match="Brevo delivery failed"):
        await provider.send(
            OutgoingEmail(
                recipient="user@example.com",
                subject="Subject",
                body="Body",
            )
        )
