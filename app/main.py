"""FastAPI application entry point."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from redis.asyncio import Redis
from starlette.responses import JSONResponse
from starlette.types import Receive, Scope, Send

from app.api.v1.router import router as api_v1_router
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.db.session import create_database_engine, create_session_factory
from app.integrations.ai.factory import create_ai_provider
from app.middleware.body_limit import BodyLimitMiddleware
from app.middleware.request_context import (
    RequestContextMiddleware,
    request_id_context,
)
from app.services.rate_limit import RedisRateLimiter


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create the FastAPI application.

    Routers and global exception handlers are added in their dedicated stages.
    """
    application_settings = settings or get_settings()
    configure_logging(application_settings)

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        engine = create_database_engine(application_settings)
        redis_client = Redis.from_url(
            application_settings.redis_url,
            decode_responses=True,
        )
        ai_http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(application_settings.ai_timeout_seconds),
        )
        application.state.engine = engine
        application.state.session_factory = create_session_factory(engine)
        application.state.redis = redis_client
        application.state.rate_limiter = RedisRateLimiter(
            redis_client,
            limit=application_settings.rate_limit_requests,
            window_seconds=application_settings.rate_limit_window_seconds,
        )
        application.state.ai_http_client = ai_http_client
        application.state.ai_provider = create_ai_provider(
            application_settings,
            ai_http_client,
        )
        yield
        await ai_http_client.aclose()
        await redis_client.aclose()
        await engine.dispose()

    application = FastAPI(
        title="AI Contact API",
        description="API for portfolio contact requests with AI classification.",
        version="0.1.0",
        lifespan=lifespan,
    )

    async def request_too_large(
        _scope: Scope,
        _receive: Receive,
        send: Send,
    ) -> None:
        request_id = request_id_context.get()
        response = JSONResponse(
            status_code=413,
            content={
                "error": {
                    "code": "request_too_large",
                    "message": "Request body is too large",
                    "details": [],
                    "request_id": request_id,
                }
            },
        )
        await response(_scope, _receive, send)

    application.add_middleware(
        BodyLimitMiddleware,
        max_bytes=application_settings.request_body_max_bytes,
        on_too_large=request_too_large,
    )
    application.add_middleware(
        RequestContextMiddleware,
        ip_hash_salt=application_settings.ip_hash_salt,
        trust_proxy_headers=application_settings.trust_proxy_headers,
    )
    application.state.settings = application_settings
    application.include_router(api_v1_router)
    return application


app = create_app()
