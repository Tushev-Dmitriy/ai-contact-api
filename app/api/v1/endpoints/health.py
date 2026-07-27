"""Service health endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from app.schemas.health import HealthResponse, LivenessResponse
from app.services.dependencies import get_health_service
from app.services.health import HealthService

router = APIRouter(prefix="/health", tags=["health"])


@router.get("", response_model=HealthResponse)
async def health(
    service: Annotated[HealthService, Depends(get_health_service)],
) -> HealthResponse:
    """Return overall status and sanitized dependency details."""
    result, _ready = await service.check()
    return result


@router.get("/live", response_model=LivenessResponse)
async def liveness() -> LivenessResponse:
    """Confirm that the application process is serving requests."""
    return LivenessResponse()


@router.get(
    "/ready",
    response_model=HealthResponse,
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": HealthResponse}},
)
async def readiness(
    response: Response,
    service: Annotated[HealthService, Depends(get_health_service)],
) -> HealthResponse:
    """Report readiness, failing only when PostgreSQL is unavailable."""
    result, ready = await service.check()
    if not ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return result
