"""Strict schemas for AI contact classification."""

from pydantic import BaseModel, ConfigDict, Field

from app.db.models.contact_request import (
    ContactCategory,
    ProviderStatus,
    Sentiment,
    Urgency,
)


class AIResponsePayload(BaseModel):
    """Structured content accepted from an external AI provider."""

    model_config = ConfigDict(extra="forbid")

    category: ContactCategory
    sentiment: Sentiment
    urgency: Urgency
    summary: str | None = Field(default=None, max_length=200)


class AIClassification(AIResponsePayload):
    """Validated classification enriched with provider availability."""

    provider_status: ProviderStatus
