"""Deterministic AI fallback provider."""

from app.db.models.contact_request import (
    ContactCategory,
    ProviderStatus,
    Sentiment,
    Urgency,
)
from app.schemas.ai import AIClassification


class FallbackAIProvider:
    """Return a safe classification without external dependencies."""

    async def classify(self, comment: str) -> AIClassification:
        """Return the documented fallback regardless of comment content."""
        del comment
        return AIClassification(
            category=ContactCategory.OTHER,
            sentiment=Sentiment.NEUTRAL,
            urgency=Urgency.LOW,
            summary=None,
            provider_status=ProviderStatus.UNAVAILABLE,
        )
