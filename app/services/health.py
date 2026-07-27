"""Dependency health checks."""

from typing import Protocol

from redis.exceptions import RedisError
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.config import Settings
from app.schemas.health import DependencyHealth, HealthResponse


class RedisHealthClient(Protocol):
    """Small Redis surface needed by readiness diagnostics."""

    async def ping(self) -> bool: ...


class HealthService:
    """Check critical and degradable dependencies independently."""

    def __init__(
        self,
        engine: AsyncEngine,
        redis: RedisHealthClient,
        settings: Settings,
    ) -> None:
        self.engine = engine
        self.redis = redis
        self.settings = settings

    async def check(self) -> tuple[HealthResponse, bool]:
        """Return detailed status and whether the service is ready."""
        postgres_up = await self._postgres_is_up()
        redis_up = await self._redis_is_up()
        ai_status = "configured" if self.settings.ai_enabled else "disabled"

        if not postgres_up:
            overall_status = "unavailable"
        elif not redis_up:
            overall_status = "degraded"
        else:
            overall_status = "ok"

        return (
            HealthResponse(
                status=overall_status,
                checks={
                    "postgres": DependencyHealth(
                        status="up" if postgres_up else "down"
                    ),
                    "redis": DependencyHealth(status="up" if redis_up else "down"),
                    "ai": DependencyHealth(status=ai_status),
                },
            ),
            postgres_up,
        )

    async def _postgres_is_up(self) -> bool:
        try:
            async with self.engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
        except (SQLAlchemyError, OSError):
            return False
        return True

    async def _redis_is_up(self) -> bool:
        try:
            return bool(await self.redis.ping())
        except (RedisError, ConnectionError, OSError, TimeoutError):
            return False
