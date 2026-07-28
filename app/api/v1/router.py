"""Version 1 API router."""

from fastapi import APIRouter

from app.api.v1.endpoints.contact import router as contact_router
from app.api.v1.endpoints.health import router as health_router
from app.api.v1.endpoints.metrics import router as metrics_router

router = APIRouter(prefix="/api")
router.include_router(contact_router)
router.include_router(health_router)
router.include_router(metrics_router)
