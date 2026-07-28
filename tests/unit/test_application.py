from pathlib import Path

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.core.config import Settings
from app.main import create_app


def build_settings(
    tmp_path: Path,
    *,
    request_body_max_bytes: int = 16_384,
) -> Settings:
    return Settings(
        app_env="test",
        app_log_file=tmp_path / "app.log",
        ip_hash_salt="test-salt",
        request_body_max_bytes=request_body_max_bytes,
    )


def test_create_app_returns_configured_fastapi_application(tmp_path: Path) -> None:
    settings = build_settings(tmp_path)
    application = create_app(settings)

    assert isinstance(application, FastAPI)
    assert application.title == "AI Contact API"
    assert application.version == "0.1.0"
    assert application.state.settings is settings


async def test_local_frontend_is_served(tmp_path: Path) -> None:
    application = create_app(build_settings(tmp_path))

    async with AsyncClient(
        transport=ASGITransport(app=application),
        base_url="http://test",
    ) as client:
        response = await client.get("/")
        script = await client.get("/app.js")

    assert response.status_code == 200
    assert "AI Contact API" in response.text
    assert "/api/contact" in response.text
    assert script.status_code == 200
    assert 'fetch("/api/contact"' in script.text


async def test_request_id_is_returned_and_safe_input_is_preserved(
    tmp_path: Path,
) -> None:
    application = create_app(build_settings(tmp_path))

    @application.get("/test")
    async def test_endpoint() -> dict[str, str]:
        return {"status": "ok"}

    async with AsyncClient(
        transport=ASGITransport(app=application),
        base_url="http://test",
    ) as client:
        response = await client.get("/test", headers={"X-Request-ID": "web_123"})

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "web_123"
    log_output = (tmp_path / "app.log").read_text(encoding="utf-8")
    assert '"message": "request_completed"' in log_output
    assert '"request_id": "web_123"' in log_output
    assert '"method": "GET"' in log_output
    assert '"path": "/test"' in log_output


async def test_unsafe_request_id_is_replaced(tmp_path: Path) -> None:
    application = create_app(build_settings(tmp_path))

    @application.get("/test")
    async def test_endpoint() -> dict[str, str]:
        return {"status": "ok"}

    async with AsyncClient(
        transport=ASGITransport(app=application),
        base_url="http://test",
    ) as client:
        response = await client.get(
            "/test",
            headers={"X-Request-ID": "unsafe\nvalue"},
        )

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] != "unsafe\nvalue"
    assert len(response.headers["X-Request-ID"]) == 36


async def test_request_body_limit_returns_error_contract(tmp_path: Path) -> None:
    application = create_app(
        build_settings(tmp_path, request_body_max_bytes=4),
    )

    @application.post("/test")
    async def test_endpoint() -> dict[str, str]:
        return {"status": "ok"}

    async with AsyncClient(
        transport=ASGITransport(app=application),
        base_url="http://test",
    ) as client:
        response = await client.post("/test", content=b"12345")

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "request_too_large"
    assert response.json()["error"]["request_id"] == response.headers["X-Request-ID"]
