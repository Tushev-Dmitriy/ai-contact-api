"""Application exceptions and global HTTP error handlers."""

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse

from app.core.config import Settings
from app.middleware.request_context import request_id_context
from app.services.rate_limit import RateLimitExceededError

logger = logging.getLogger(__name__)


class BusinessRequestError(Exception):
    """A safe client-visible business rule violation."""

    def __init__(self, message: str, *, code: str = "bad_request") -> None:
        super().__init__(message)
        self.message = message
        self.code = code


def error_response(
    request: Request,
    *,
    status_code: int,
    code: str,
    message: str,
    details: list[dict[str, Any]] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    """Build the one public error envelope used by the API."""
    request_id = getattr(request.state, "request_id", request_id_context.get())
    response_headers = dict(headers or {})
    if request_id:
        response_headers["X-Request-ID"] = request_id
    return JSONResponse(
        status_code=status_code,
        headers=response_headers,
        content={
            "error": {
                "code": code,
                "message": message,
                "details": details or [],
                "request_id": request_id,
            }
        },
    )


def register_exception_handlers(app: FastAPI, settings: Settings) -> None:
    """Register safe handlers from most specific to generic."""

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request,
        error: RequestValidationError,
    ) -> JSONResponse:
        details = [
            {
                "location": list(item["loc"]),
                "message": item["msg"],
                "type": item["type"],
            }
            for item in error.errors()
        ]
        return error_response(
            request,
            status_code=422,
            code="validation_error",
            message="Request validation failed",
            details=details,
        )

    @app.exception_handler(RateLimitExceededError)
    async def rate_limit_error_handler(
        request: Request,
        error: RateLimitExceededError,
    ) -> JSONResponse:
        return error_response(
            request,
            status_code=429,
            code="rate_limit_exceeded",
            message="Contact request rate limit exceeded",
            headers={"Retry-After": str(error.retry_after_seconds)},
        )

    @app.exception_handler(BusinessRequestError)
    async def business_error_handler(
        request: Request,
        error: BusinessRequestError,
    ) -> JSONResponse:
        return error_response(
            request,
            status_code=400,
            code=error.code,
            message=error.message,
        )

    @app.exception_handler(HTTPException)
    async def http_error_handler(
        request: Request,
        error: HTTPException,
    ) -> JSONResponse:
        message = error.detail if isinstance(error.detail, str) else "HTTP error"
        return error_response(
            request,
            status_code=error.status_code,
            code="not_found" if error.status_code == 404 else "http_error",
            message=message,
            headers=dict(error.headers) if error.headers else None,
        )

    @app.exception_handler(SQLAlchemyError)
    async def database_error_handler(
        request: Request,
        error: SQLAlchemyError,
    ) -> JSONResponse:
        logger.error(
            "database_operation_failed",
            extra={"error_type": type(error).__name__},
        )
        return error_response(
            request,
            status_code=503,
            code="database_unavailable",
            message="A critical dependency is unavailable",
        )

    @app.exception_handler(Exception)
    async def unknown_error_handler(
        request: Request,
        error: Exception,
    ) -> JSONResponse:
        if settings.app_env == "development":
            logger.error(
                "unhandled_application_error",
                exc_info=(type(error), error, error.__traceback__),
            )
        else:
            logger.error(
                "unhandled_application_error",
                extra={"error_type": type(error).__name__},
            )
        return error_response(
            request,
            status_code=500,
            code="internal_error",
            message="An unexpected error occurred",
        )
