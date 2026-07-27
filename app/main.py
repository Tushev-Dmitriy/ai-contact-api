"""FastAPI application entry point."""

from fastapi import FastAPI
from starlette.responses import JSONResponse
from starlette.types import Receive, Scope, Send

from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.middleware.body_limit import BodyLimitMiddleware
from app.middleware.request_context import (
    RequestContextMiddleware,
    request_id_context,
)


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create the FastAPI application.

    Routers and global exception handlers are added in their dedicated stages.
    """
    application_settings = settings or get_settings()
    configure_logging(application_settings)

    application = FastAPI(
        title="AI Contact API",
        description="API for portfolio contact requests with AI classification.",
        version="0.1.0",
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
    return application


app = create_app()
