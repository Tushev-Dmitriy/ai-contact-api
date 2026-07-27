"""Product metrics endpoint schema."""

from pydantic import BaseModel


class ContactMetrics(BaseModel):
    """Aggregated non-personal contact statistics."""

    total_requests: int
    requests_today: int
    categories: dict[str, int]
    sentiment: dict[str, int]
    email_failures: int
    ai_fallback_count: int
