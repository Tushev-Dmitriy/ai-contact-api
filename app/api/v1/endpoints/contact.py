"""Contact request endpoint."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.db.dependencies import get_session
from app.integrations.ai.base import AIProvider
from app.middleware.request_context import client_ip
from app.repositories.contact import ContactRequestRepository
from app.schemas.contact import ContactAccepted, ContactCreate
from app.services.contact import ContactService
from app.services.dependencies import get_ai_provider, get_rate_limiter
from app.services.rate_limit import RateLimitExceededError, RedisRateLimiter
from app.utils.pii import hash_ip

router = APIRouter(prefix="/contact", tags=["contact"])


@router.post(
    "",
    response_model=ContactAccepted,
    response_model_exclude_none=True,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Submit a contact request",
)
async def create_contact(
    payload: ContactCreate,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    rate_limiter: Annotated[RedisRateLimiter, Depends(get_rate_limiter)],
    ai_provider: Annotated[AIProvider, Depends(get_ai_provider)],
) -> ContactAccepted:
    """Validate, normalize, and persist a new contact request."""
    settings: Settings = request.app.state.settings
    source_ip = client_ip(
        request,
        trust_proxy_headers=settings.trust_proxy_headers,
    )
    source_ip_hash = hash_ip(source_ip, salt=settings.ip_hash_salt)
    if source_ip_hash:
        try:
            await rate_limiter.enforce(source_ip_hash)
        except RateLimitExceededError as error:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Contact request rate limit exceeded",
                headers={"Retry-After": str(error.retry_after_seconds)},
            ) from error

    service = ContactService(ContactRequestRepository(session), ai_provider)
    contact = await service.accept(
        payload,
        source_ip_hash=source_ip_hash,
        user_agent=request.headers.get("user-agent"),
    )
    return ContactAccepted(
        request_id=contact.id,
        category=contact.category.value if contact.category else None,
    )
