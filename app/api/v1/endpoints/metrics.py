"""Protected product metrics endpoint."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import require_metrics_api_key
from app.db.dependencies import get_session
from app.repositories.metrics import MetricsRepository
from app.schemas.metrics import ContactMetrics

router = APIRouter(tags=["metrics"])


@router.get(
    "/metrics",
    response_model=ContactMetrics,
    dependencies=[Depends(require_metrics_api_key)],
)
async def metrics(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ContactMetrics:
    """Return aggregate contact statistics without personal data."""
    return await MetricsRepository(session).get_contact_metrics()
