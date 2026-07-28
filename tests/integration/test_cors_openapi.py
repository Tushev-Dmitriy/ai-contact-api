from pathlib import Path

from httpx import ASGITransport, AsyncClient

from app.core.config import Settings
from app.main import create_app


def build_settings(tmp_path: Path) -> Settings:
    return Settings(
        app_env="test",
        app_log_file=tmp_path / "app.log",
        ip_hash_salt="integration-test-salt",
        cors_allowed_origins=["https://portfolio.example"],
    )


async def test_cors_allows_only_configured_origin(tmp_path: Path) -> None:
    application = create_app(build_settings(tmp_path))

    async with AsyncClient(
        transport=ASGITransport(app=application),
        base_url="http://test",
    ) as client:
        allowed = await client.options(
            "/api/contact",
            headers={
                "Origin": "https://portfolio.example",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type,x-request-id",
            },
        )
        denied = await client.options(
            "/api/contact",
            headers={
                "Origin": "https://attacker.example",
                "Access-Control-Request-Method": "POST",
            },
        )

    assert allowed.status_code == 200
    assert allowed.headers["Access-Control-Allow-Origin"] == "https://portfolio.example"
    assert allowed.headers["Access-Control-Allow-Credentials"] == "true"
    assert denied.status_code == 400
    assert "Access-Control-Allow-Origin" not in denied.headers


async def test_openapi_exposes_only_pdf_routes(tmp_path: Path) -> None:
    application = create_app(build_settings(tmp_path))

    async with AsyncClient(
        transport=ASGITransport(app=application),
        base_url="http://test",
    ) as client:
        response = await client.get("/openapi.json")

    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/api/contact" in paths
    assert "/api/health" in paths
    assert "/api/health/live" in paths
    assert "/api/health/ready" in paths
    assert "/api/metrics" in paths
    assert all("/api/v1/" not in path for path in paths)
