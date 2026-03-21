# ruff: noqa: INP001
"""Integration tests for silo blueprint read APIs."""

from __future__ import annotations

import pytest
from fastapi import APIRouter, FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.silo_blueprints import router as silo_blueprints_router


def _build_test_app() -> FastAPI:
    app = FastAPI()
    api_v1 = APIRouter(prefix="/api/v1")
    api_v1.include_router(silo_blueprints_router)
    app.include_router(api_v1)
    return app


@pytest.mark.asyncio
async def test_list_silo_blueprints_returns_default_four_agent_blueprint() -> None:
    app = _build_test_app()

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.get("/api/v1/silo-blueprints")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["slug"] == "default-four-agent"
    assert body[0]["supports_symphony"] is True
    assert body[0]["supports_telemetry"] is True


@pytest.mark.asyncio
async def test_get_silo_blueprint_returns_matching_blueprint() -> None:
    app = _build_test_app()

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.get("/api/v1/silo-blueprints/default-four-agent")

    assert response.status_code == 200
    body = response.json()
    assert body["slug"] == "default-four-agent"
    assert [role["slug"] for role in body["roles"]] == [
        "fox",
        "bunny",
        "owl",
        "otter",
        "symphony",
    ]


@pytest.mark.asyncio
async def test_get_silo_blueprint_returns_404_for_unknown_slug() -> None:
    app = _build_test_app()

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.get("/api/v1/silo-blueprints/unknown-blueprint")

    assert response.status_code == 404
    assert response.json()["detail"] == "Blueprint not found"
