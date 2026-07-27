"""AI provider construction."""

import httpx

from app.core.config import Settings
from app.integrations.ai.base import AIProvider
from app.integrations.ai.fallback import FallbackAIProvider
from app.integrations.ai.openai_compatible import (
    FallbackOnErrorProvider,
    OpenAICompatibleProvider,
)


def create_ai_provider(
    settings: Settings,
    client: httpx.AsyncClient,
) -> AIProvider:
    """Select fallback-only or resilient external classification."""
    fallback = FallbackAIProvider()
    if not settings.ai_enabled:
        return fallback

    if not settings.ai_api_key or not settings.ai_model:
        raise ValueError("Enabled AI configuration was not validated")

    primary = OpenAICompatibleProvider(
        client,
        base_url=str(settings.ai_base_url),
        api_key=settings.ai_api_key,
        model=settings.ai_model,
    )
    return FallbackOnErrorProvider(primary, fallback)
