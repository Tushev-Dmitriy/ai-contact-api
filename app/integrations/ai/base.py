"""AI provider contract."""

from typing import Protocol

from app.schemas.ai import AIClassification


class AIProvider(Protocol):
    """Replaceable contact classification provider."""

    async def classify(self, comment: str) -> AIClassification:
        """Classify one user comment."""
        ...
