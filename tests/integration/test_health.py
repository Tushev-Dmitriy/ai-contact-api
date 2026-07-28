from pathlib import Path
from typing import cast

from httpx import ASGITransport, AsyncClient

from app.core.config import Settings
from app.main import create_app
from app.schemas.health import DependencyHealth, HealthResponse
from app.services.dependencies import get_health_service
from app.services.health import HealthService


class StaticHealthService:
    def __init__(self, result: HealthResponse, *, ready: bool) -> None:
        self.result = result
        self.ready = ready

    async def check(self) -> tuple[HealthResponse, bool]:
        return self.result, self.ready


def build_settings(tmp_path: Path) -> Settings:
    return Settings(
        app_env="test",
        app_log_file=tmp_path / "app.log",
        ip_hash_salt="integration-test-salt",
    )


async def test_liveness_does_not_require_dependencies(tmp_path: Path) -> None:
    application = create_app(build_settings(tmp_path))

    async with AsyncClient(
        transport=ASGITransport(app=application),
        base_url="http://test",
    ) as client:
        response = await client.get("/api/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_readiness_is_degraded_but_ready_when_only_redis_is_down(
    tmp_path: Path,
) -> None:
    application = create_app(build_settings(tmp_path))
    service = StaticHealthService(
        HealthResponse(
            status="degraded",
            checks={
                "postgres": DependencyHealth(status="up"),
                "redis": DependencyHealth(status="down"),
                "ai": DependencyHealth(status="disabled"),
            },
        ),
        ready=True,
    )
    application.dependency_overrides[get_health_service] = lambda: cast(
        HealthService,
        service,
    )

    async with AsyncClient(
        transport=ASGITransport(app=application),
        base_url="http://test",
    ) as client:
        response = await client.get("/api/health/ready")

    assert response.status_code == 200
    assert response.json()["status"] == "degraded"
    assert response.json()["checks"]["redis"]["status"] == "down"


async def test_readiness_returns_503_when_postgres_is_down(tmp_path: Path) -> None:
    application = create_app(build_settings(tmp_path))
    service = StaticHealthService(
        HealthResponse(
            status="unavailable",
            checks={
                "postgres": DependencyHealth(status="down"),
                "redis": DependencyHealth(status="up"),
                "ai": DependencyHealth(status="configured"),
            },
        ),
        ready=False,
    )
    application.dependency_overrides[get_health_service] = lambda: cast(
        HealthService,
        service,
    )

    async with AsyncClient(
        transport=ASGITransport(app=application),
        base_url="http://test",
    ) as client:
        response = await client.get("/api/health/ready")

    assert response.status_code == 503
    assert response.json()["checks"]["postgres"]["status"] == "down"
    assert "url" not in response.text.lower()
