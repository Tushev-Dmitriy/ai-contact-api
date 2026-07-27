"""Redis-backed contact request rate limiting."""

import logging
from dataclasses import dataclass
from typing import Protocol

from redis.exceptions import RedisError

logger = logging.getLogger(__name__)

RATE_LIMIT_SCRIPT = """
local current = redis.call("INCR", KEYS[1])
if current == 1 then
    redis.call("EXPIRE", KEYS[1], ARGV[1])
end
local ttl = redis.call("TTL", KEYS[1])
return {current, ttl}
"""


class RedisScriptClient(Protocol):
    """Small Redis surface needed by the limiter."""

    async def eval(
        self,
        script: str,
        numkeys: int,
        *keys_and_args: object,
    ) -> object: ...


@dataclass(frozen=True, slots=True)
class RateLimitResult:
    """Outcome of a rate-limit check."""

    allowed: bool
    remaining: int
    retry_after_seconds: int
    backend_available: bool = True


class RateLimitExceededError(Exception):
    """Raised when a contact identity has exhausted its request allowance."""

    def __init__(self, *, retry_after_seconds: int) -> None:
        super().__init__("Contact request rate limit exceeded")
        self.retry_after_seconds = retry_after_seconds


class RedisRateLimiter:
    """Atomic fixed-window limiter using a Redis counter with TTL."""

    def __init__(
        self,
        client: RedisScriptClient,
        *,
        limit: int,
        window_seconds: int,
    ) -> None:
        self.client = client
        self.limit = limit
        self.window_seconds = window_seconds

    async def check(self, identity_hash: str) -> RateLimitResult:
        """Increment a hashed identity counter and return its allowance."""
        key = f"contact-rate-limit:{identity_hash}"
        try:
            raw_result = await self.client.eval(
                RATE_LIMIT_SCRIPT,
                1,
                key,
                self.window_seconds,
            )
            count, ttl = self._parse_result(raw_result)
        except (RedisError, ConnectionError, TimeoutError, ValueError, TypeError):
            logger.warning(
                "rate_limit_backend_unavailable",
                extra={"backend": "redis"},
            )
            return RateLimitResult(
                allowed=True,
                remaining=self.limit,
                retry_after_seconds=0,
                backend_available=False,
            )

        retry_after = ttl if ttl > 0 else self.window_seconds
        return RateLimitResult(
            allowed=count <= self.limit,
            remaining=max(self.limit - count, 0),
            retry_after_seconds=retry_after,
        )

    async def enforce(self, identity_hash: str) -> RateLimitResult:
        """Raise a typed error when the limit is exceeded."""
        result = await self.check(identity_hash)
        if not result.allowed:
            raise RateLimitExceededError(
                retry_after_seconds=result.retry_after_seconds,
            )
        return result

    @staticmethod
    def _parse_result(raw_result: object) -> tuple[int, int]:
        if not isinstance(raw_result, (list, tuple)) or len(raw_result) != 2:
            raise ValueError("Unexpected Redis rate-limit result")
        return int(raw_result[0]), int(raw_result[1])
