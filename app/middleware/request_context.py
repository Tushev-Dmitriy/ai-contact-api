"""Request context and access logging middleware."""

import logging
import re
import time
from contextvars import ContextVar
from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from app.utils.pii import hash_ip

REQUEST_ID_HEADER = "X-Request-ID"
REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
request_id_context: ContextVar[str | None] = ContextVar(
    "request_id",
    default=None,
)
logger = logging.getLogger("app.requests")


def safe_request_id(value: str | None) -> str:
    """Use a caller-provided request ID only when it is safe for logs/headers."""
    if value and REQUEST_ID_PATTERN.fullmatch(value):
        return value
    return str(uuid4())


def client_ip(request: Request, *, trust_proxy_headers: bool) -> str | None:
    """Return the effective client IP according to the proxy trust policy."""
    if trust_proxy_headers:
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            candidate = forwarded_for.split(",", maxsplit=1)[0].strip()
            if candidate:
                return candidate
    return request.client.host if request.client else None


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Set request ID, log request completion, and return the ID to clients."""

    def __init__(
        self,
        app: ASGIApp,
        *,
        ip_hash_salt: str,
        trust_proxy_headers: bool,
    ) -> None:
        super().__init__(app)
        self.ip_hash_salt = ip_hash_salt
        self.trust_proxy_headers = trust_proxy_headers

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        request_id = safe_request_id(request.headers.get(REQUEST_ID_HEADER))
        request.state.request_id = request_id
        token = request_id_context.set(request_id)
        started_at = time.perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            response.headers[REQUEST_ID_HEADER] = request_id
            return response
        finally:
            duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
            source_ip = client_ip(
                request,
                trust_proxy_headers=self.trust_proxy_headers,
            )
            logger.info(
                "request_completed",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "status": status_code,
                    "duration_ms": duration_ms,
                    "ip_hash": hash_ip(source_ip, salt=self.ip_hash_salt),
                },
            )
            request_id_context.reset(token)
