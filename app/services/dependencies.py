"""FastAPI application service dependencies."""

from typing import cast

from fastapi import Request

from app.services.rate_limit import RedisRateLimiter


def get_rate_limiter(request: Request) -> RedisRateLimiter:
    """Return the application rate limiter."""
    return cast(RedisRateLimiter, request.app.state.rate_limiter)
