import logging

import pytest
from redis.exceptions import ConnectionError as RedisConnectionError

from app.services.rate_limit import (
    RateLimitExceededError,
    RedisRateLimiter,
)


class FakeRedis:
    def __init__(self, result: object) -> None:
        self.result = result
        self.calls: list[tuple[object, ...]] = []

    async def eval(
        self,
        script: str,
        numkeys: int,
        *keys_and_args: object,
    ) -> object:
        self.calls.append((script, numkeys, *keys_and_args))
        if isinstance(self.result, BaseException):
            raise self.result
        return self.result


async def test_rate_limiter_allows_requests_with_remaining_capacity() -> None:
    redis = FakeRedis([2, 700])
    limiter = RedisRateLimiter(redis, limit=5, window_seconds=900)

    result = await limiter.enforce("hashed-ip")

    assert result.allowed is True
    assert result.remaining == 3
    assert result.retry_after_seconds == 700
    assert redis.calls[0][2:] == ("contact-rate-limit:hashed-ip", 900)


async def test_rate_limiter_raises_with_retry_after_when_exceeded() -> None:
    limiter = RedisRateLimiter(
        FakeRedis([6, 321]),
        limit=5,
        window_seconds=900,
    )

    with pytest.raises(RateLimitExceededError) as caught:
        await limiter.enforce("hashed-ip")

    assert caught.value.retry_after_seconds == 321


async def test_rate_limiter_fails_open_when_redis_is_unavailable(
    caplog: pytest.LogCaptureFixture,
) -> None:
    limiter = RedisRateLimiter(
        FakeRedis(RedisConnectionError("redis unavailable")),
        limit=5,
        window_seconds=900,
    )

    with caplog.at_level(logging.WARNING):
        result = await limiter.enforce("hashed-ip")

    assert result.allowed is True
    assert result.backend_available is False
    assert "rate_limit_backend_unavailable" in caplog.text
    assert "hashed-ip" not in caplog.text
