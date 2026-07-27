"""ASGI request body size limiting middleware."""

from collections.abc import Awaitable, Callable

from starlette.datastructures import Headers
from starlette.types import ASGIApp, Message, Receive, Scope, Send

RequestBodyTooLargeHandler = Callable[[Scope, Receive, Send], Awaitable[None]]


class RequestBodyTooLargeError(Exception):
    """Raised internally when the ASGI body exceeds the configured limit."""


class BodyLimitMiddleware:
    """Reject HTTP request bodies that exceed the configured byte limit."""

    def __init__(
        self,
        app: ASGIApp,
        *,
        max_bytes: int,
        on_too_large: RequestBodyTooLargeHandler,
    ) -> None:
        self.app = app
        self.max_bytes = max_bytes
        self.on_too_large = on_too_large

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        content_length = Headers(scope=scope).get("content-length")
        if content_length is not None:
            try:
                if int(content_length) > self.max_bytes:
                    await self.on_too_large(scope, receive, send)
                    return
            except ValueError:
                pass

        received_bytes = 0

        async def limited_receive() -> Message:
            nonlocal received_bytes
            message = await receive()
            if message["type"] == "http.request":
                received_bytes += len(message.get("body", b""))
                if received_bytes > self.max_bytes:
                    raise RequestBodyTooLargeError
            return message

        try:
            await self.app(scope, limited_receive, send)
        except RequestBodyTooLargeError:
            await self.on_too_large(scope, receive, send)
