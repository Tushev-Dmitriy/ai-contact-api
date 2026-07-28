"""Small API security helpers."""

import hashlib
import hmac
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from app.core.config import Settings

admin_basic = HTTPBasic(auto_error=False)


def secrets_match(provided: str, expected: str) -> bool:
    """Compare fixed-size digests to avoid key-length timing differences."""
    provided_digest = hashlib.sha256(provided.encode()).digest()
    expected_digest = hashlib.sha256(expected.encode()).digest()
    return hmac.compare_digest(provided_digest, expected_digest)


def require_metrics_api_key(
    request: Request,
    x_api_key: str | None = Header(default=None),
) -> None:
    """Hide metrics when disabled or when authentication fails."""
    settings: Settings = request.app.state.settings
    if (
        not settings.metrics_api_key
        or not x_api_key
        or not secrets_match(x_api_key, settings.metrics_api_key)
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Not Found",
        )


def require_admin(
    request: Request,
    credentials: Annotated[HTTPBasicCredentials | None, Depends(admin_basic)],
) -> None:
    """Protect local contact data with simple configurable HTTP Basic auth."""
    settings: Settings = request.app.state.settings
    if (
        credentials is None
        or not secrets_match(credentials.username, settings.admin_username)
        or not secrets_match(credentials.password, settings.admin_password)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin credentials",
            headers={"WWW-Authenticate": 'Basic realm="AI Contact Admin"'},
        )
