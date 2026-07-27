"""Version 1 API router."""

from fastapi import APIRouter

from app.api.v1.endpoints.contact import router as contact_router

router = APIRouter(prefix="/api/v1")
router.include_router(contact_router)
