"""Contact request endpoint."""

from typing import Annotated, cast

from fastapi import APIRouter, BackgroundTasks, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.db.dependencies import get_session
from app.integrations.ai.base import AIProvider
from app.middleware.request_context import client_ip
from app.repositories.contact import ContactRequestRepository
from app.schemas.contact import ContactAccepted, ContactCreate
from app.services.contact import ContactService
from app.services.dependencies import (
    get_ai_provider,
    get_email_service,
    get_rate_limiter,
)
from app.services.email import EmailService, process_contact_emails
from app.services.rate_limit import RedisRateLimiter
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
    background_tasks: BackgroundTasks,
    session: Annotated[AsyncSession, Depends(get_session)],
    rate_limiter: Annotated[RedisRateLimiter, Depends(get_rate_limiter)],
    ai_provider: Annotated[AIProvider, Depends(get_ai_provider)],
    email_service: Annotated[EmailService, Depends(get_email_service)],
) -> ContactAccepted:
    """Validate, normalize, and persist a new contact request."""
    settings: Settings = request.app.state.settings
    source_ip = client_ip(
        request,
        trust_proxy_headers=settings.trust_proxy_headers,
    )
    source_ip_hash = hash_ip(source_ip, salt=settings.ip_hash_salt)
    if source_ip_hash:
        await rate_limiter.enforce(source_ip_hash)

    service = ContactService(ContactRequestRepository(session), ai_provider)
    contact = await service.create(
        payload,
        source_ip_hash=source_ip_hash,
        user_agent=request.headers.get("user-agent"),
    )
    await session.commit()
    await service.classify(contact, payload.comment)
    await session.commit()

    session_factory = cast(
        async_sessionmaker[AsyncSession],
        request.app.state.session_factory,
    )
    background_tasks.add_task(
        process_contact_emails,
        contact.id,
        session_factory,
        email_service,
    )
    return ContactAccepted(
        request_id=contact.id,
        category=contact.category.value if contact.category else None,
    )
