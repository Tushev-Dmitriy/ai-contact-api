"""FastAPI application service dependencies."""

from typing import cast

from fastapi import Request

from app.integrations.ai.base import AIProvider
from app.services.email import EmailService
from app.services.health import HealthService
from app.services.rate_limit import RedisRateLimiter


def get_rate_limiter(request: Request) -> RedisRateLimiter:
    """Return the application rate limiter."""
    return cast(RedisRateLimiter, request.app.state.rate_limiter)


def get_ai_provider(request: Request) -> AIProvider:
    """Return the configured resilient AI provider."""
    return cast(AIProvider, request.app.state.ai_provider)


def get_email_service(request: Request) -> EmailService:
    """Return the configured email service."""
    return cast(EmailService, request.app.state.email_service)


def get_health_service(request: Request) -> HealthService:
    """Return dependency health checks."""
    return cast(HealthService, request.app.state.health_service)
