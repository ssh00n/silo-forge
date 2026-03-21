# ruff: noqa: INP001
"""Integration tests for silo detail APIs."""

from __future__ import annotations

from uuid import uuid4

import httpx
import pytest
from fastapi import APIRouter, FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import require_org_admin
from app.api.silo_runtime import router as silo_runtime_router
from app.api.silos import router as silos_router
from app.db.session import get_session
from app.models.gateways import Gateway
from app.models.organizations import Organization
from app.models.organization_members import OrganizationMember
from app.models.users import User
from app.services.organizations import OrganizationContext


async def _make_engine() -> tuple[object, async_sessionmaker[AsyncSession]]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    return engine, async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


def _build_test_app(
    session_maker: async_sessionmaker[AsyncSession],
    ctx: OrganizationContext,
) -> FastAPI:
    app = FastAPI()
    api_v1 = APIRouter(prefix="/api/v1")
    api_v1.include_router(silos_router)
    api_v1.include_router(silo_runtime_router)
    app.include_router(api_v1)

    async def _override_get_session() -> AsyncSession:
        async with session_maker() as session:
            yield session

    async def _override_require_org_admin() -> OrganizationContext:
        return ctx

    app.dependency_overrides[get_session] = _override_get_session
    app.dependency_overrides[require_org_admin] = _override_require_org_admin
    return app


async def _seed_org_context(session: AsyncSession) -> tuple[OrganizationContext, Gateway]:
    user = User(
        id=uuid4(),
        clerk_user_id=f"clerk_{uuid4().hex}",
        email="admin@example.com",
        name="Admin",
    )
    organization = Organization(id=uuid4(), name="Personal")
    membership = OrganizationMember(
        id=uuid4(),
        organization_id=organization.id,
        user_id=user.id,
        role="owner",
        all_boards_read=True,
        all_boards_write=True,
    )
    gateway = Gateway(
        id=uuid4(),
        organization_id=organization.id,
        name="Fox Host",
        url="http://gateway.local",
        workspace_root="/srv/openclaw",
    )
    session.add(user)
    session.add(organization)
    session.add(membership)
    session.add(gateway)
    await session.commit()
    return OrganizationContext(organization=organization, member=membership), gateway


@pytest.mark.asyncio
async def test_get_silo_detail_returns_roles_and_plan() -> None:
    engine, session_maker = await _make_engine()
    async with session_maker() as session:
        ctx, gateway = await _seed_org_context(session)
    app = _build_test_app(session_maker, ctx)

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
            create_response = await client.post(
                "/api/v1/silos",
                json={
                    "name": "Demo Silo",
                    "blueprint_slug": "default-four-agent",
                    "gateway_assignments": [{"role_slug": "fox", "gateway_id": str(gateway.id)}],
                },
            )
            assert create_response.status_code == 201

            response = await client.get("/api/v1/silos/demo-silo/detail")

        assert response.status_code == 200
        body = response.json()
        assert body["silo"]["slug"] == "demo-silo"
        assert len(body["roles"]) == 4
        assert body["desired_state"]["roles"][0]["slug"] == body["roles"][0]["slug"]
        assert body["provision_plan"]["preview"]["slug"] == "demo-silo"
        assert len(body["provision_plan"]["targets"]) == 4
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_get_silo_detail_includes_latest_runtime_operation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine, session_maker = await _make_engine()
    async with session_maker() as session:
        ctx, gateway = await _seed_org_context(session)
    app = _build_test_app(session_maker, ctx)

    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "valid": True,
                "restart_required": True,
                "warnings": [],
                "writes": [],
                "resolved_secrets": [],
            },
        )

    original_async_client = httpx.AsyncClient
    monkeypatch.setattr(
        "app.services.silos.runtime_apply.httpx.AsyncClient",
        lambda **kwargs: original_async_client(transport=httpx.MockTransport(handler)),
    )

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
            create_response = await client.post(
                "/api/v1/silos",
                json={
                    "name": "Demo Silo",
                    "blueprint_slug": "default-four-agent",
                    "gateway_assignments": [{"role_slug": "fox", "gateway_id": str(gateway.id)}],
                },
            )
            assert create_response.status_code == 201

            runtime_response = await client.post("/api/v1/silos/demo-silo/runtime/validate")
            assert runtime_response.status_code == 200

            detail_response = await client.get("/api/v1/silos/demo-silo/detail")

        assert detail_response.status_code == 200
        body = detail_response.json()
        assert body["latest_runtime_operation"] is not None
        assert body["latest_runtime_operation"]["mode"] == "validate"
        fox = next(
            item
            for item in body["latest_runtime_operation"]["results"]
            if item["role_slug"] == "fox"
        )
        assert fox["validated"]["valid"] is True
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_get_silo_detail_returns_404_for_unknown_slug() -> None:
    engine, session_maker = await _make_engine()
    async with session_maker() as session:
        ctx, _ = await _seed_org_context(session)
    app = _build_test_app(session_maker, ctx)

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
            response = await client.get("/api/v1/silos/missing/detail")

        assert response.status_code == 404
        assert response.json()["detail"] == "Silo not found"
    finally:
        await engine.dispose()
