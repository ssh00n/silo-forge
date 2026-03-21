# ruff: noqa: INP001
"""Integration tests for silo preview APIs."""

from __future__ import annotations

import pytest
from fastapi import APIRouter, FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.silos import router as silos_router


def _build_test_app() -> FastAPI:
    app = FastAPI()
    api_v1 = APIRouter(prefix="/api/v1")
    api_v1.include_router(silos_router)
    app.include_router(api_v1)
    return app


@pytest.mark.asyncio
async def test_preview_silo_returns_desired_state_without_optional_symphony() -> None:
    app = _build_test_app()

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.post(
            "/api/v1/silos/preview",
            json={
                "name": "Demo Silo",
                "blueprint_slug": "default-four-agent",
                "enable_symphony": False,
                "enable_telemetry": True,
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["slug"] == "demo-silo"
    assert body["enable_symphony"] is False
    assert body["enable_telemetry"] is True
    assert [role["slug"] for role in body["roles"]] == ["fox", "bunny", "owl", "otter"]
    assert any("Skipping optional role symphony" in warning for warning in body["warnings"])


@pytest.mark.asyncio
async def test_preview_silo_includes_symphony_when_enabled() -> None:
    app = _build_test_app()

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.post(
            "/api/v1/silos/preview",
            json={
                "name": "Full Silo",
                "blueprint_slug": "default-four-agent",
                "enable_symphony": True,
                "enable_telemetry": True,
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert [role["slug"] for role in body["roles"]] == [
        "fox",
        "bunny",
        "owl",
        "otter",
        "symphony",
    ]


@pytest.mark.asyncio
async def test_preview_silo_returns_404_for_unknown_blueprint() -> None:
    app = _build_test_app()

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.post(
            "/api/v1/silos/preview",
            json={"name": "Broken", "blueprint_slug": "missing"},
        )

    assert response.status_code == 404
    assert response.json()["detail"] == "Unknown blueprint: missing"
