"""FastAPI application service dependencies."""

from typing import cast

from fastapi import Request

from app.integrations.ai.base import AIProvider
from app.services.rate_limit import RedisRateLimiter


def get_rate_limiter(request: Request) -> RedisRateLimiter:
    """Return the application rate limiter."""
    return cast(RedisRateLimiter, request.app.state.rate_limiter)


def get_ai_provider(request: Request) -> AIProvider:
    """Return the configured resilient AI provider."""
    return cast(AIProvider, request.app.state.ai_provider)
