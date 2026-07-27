"""Public API error schemas."""

from typing import Any

from pydantic import BaseModel


class ErrorBody(BaseModel):
    """Stable public error payload."""

    code: str
    message: str
    details: list[dict[str, Any]]
    request_id: str | None


class ErrorResponse(BaseModel):
    """Top-level API error envelope."""

    error: ErrorBody
