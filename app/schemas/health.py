"""Health endpoint schemas."""

from typing import Literal

from pydantic import BaseModel


class DependencyHealth(BaseModel):
    """One dependency's sanitized health state."""

    status: Literal["up", "down", "disabled", "configured"]


class HealthResponse(BaseModel):
    """Detailed service health without internal URLs or secrets."""

    status: Literal["ok", "degraded", "unavailable"]
    checks: dict[str, DependencyHealth]


class LivenessResponse(BaseModel):
    """Minimal process liveness response."""

    status: Literal["ok"] = "ok"
