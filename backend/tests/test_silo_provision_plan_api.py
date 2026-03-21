# ruff: noqa: INP001
"""Integration tests for silo provision-plan preview APIs."""

from __future__ import annotations

import pytest
from fastapi import APIRouter, FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.silo_provision_plans import router as silo_provision_plans_router


def _build_test_app() -> FastAPI:
    app = FastAPI()
    api_v1 = APIRouter(prefix="/api/v1")
    api_v1.include_router(silo_provision_plans_router)
    app.include_router(api_v1)
    return app


@pytest.mark.asyncio
async def test_preview_silo_provision_plan_returns_gateway_bundle_targets() -> None:
    app = _build_test_app()

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.post(
            "/api/v1/silo-provision-plans/preview",
            json={
                "name": "Demo Silo",
                "blueprint_slug": "default-four-agent",
                "enable_symphony": False,
                "enable_telemetry": True,
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert len(body["targets"]) == 4
    first_target = body["targets"][0]
    assert first_target["supports_picoclaw_bundle_apply"] is True
    assert first_target["bundle"]["config_patch"]["channels"]["discord"]["token"] == {
        "$secret": "fox_discord_bot_token"
    }
    assert first_target["bundle"]["files"][0]["path"] == "AGENTS.md"
    assert first_target["bundle"]["secret_bindings"][0]["env_var"] == "ANTHROPIC_API_KEY"


@pytest.mark.asyncio
async def test_preview_silo_provision_plan_marks_symphony_target_as_unsupported() -> None:
    app = _build_test_app()

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.post(
            "/api/v1/silo-provision-plans/preview",
            json={
                "name": "Full Silo",
                "blueprint_slug": "default-four-agent",
                "enable_symphony": True,
                "enable_telemetry": True,
            },
        )

    assert response.status_code == 200
    body = response.json()
    symphony_target = next(target for target in body["targets"] if target["role_slug"] == "symphony")
    assert symphony_target["supports_picoclaw_bundle_apply"] is False
    assert symphony_target["bundle"] is None
    assert "not yet rendered" in symphony_target["warnings"][0]


@pytest.mark.asyncio
async def test_preview_silo_provision_plan_returns_404_for_unknown_blueprint() -> None:
    app = _build_test_app()

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.post(
            "/api/v1/silo-provision-plans/preview",
            json={"name": "Broken", "blueprint_slug": "missing"},
        )

    assert response.status_code == 404
    assert response.json()["detail"] == "Unknown blueprint: missing"
