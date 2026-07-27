"""Contact request endpoint."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.db.dependencies import get_session
from app.middleware.request_context import client_ip
from app.repositories.contact import ContactRequestRepository
from app.schemas.contact import ContactAccepted, ContactCreate
from app.services.contact import ContactService
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
) -> ContactAccepted:
    """Validate, normalize, and persist a new contact request."""
    settings: Settings = request.app.state.settings
    source_ip = client_ip(
        request,
        trust_proxy_headers=settings.trust_proxy_headers,
    )
    service = ContactService(ContactRequestRepository(session))
    contact = await service.accept(
        payload,
        source_ip_hash=hash_ip(source_ip, salt=settings.ip_hash_salt),
        user_agent=request.headers.get("user-agent"),
    )
    return ContactAccepted(request_id=contact.id)
