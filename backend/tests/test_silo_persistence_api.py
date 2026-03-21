# ruff: noqa: INP001
"""Integration tests for persisted silo APIs."""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi import APIRouter, FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import require_org_admin
from app.api.silos import router as silos_router
from app.db.session import get_session
from app.models.gateways import Gateway
from app.models.organizations import Organization
from app.models.organization_members import OrganizationMember
from app.models.users import User
from app.services.organizations import OrganizationContext


async def _make_engine() -> AsyncEngine:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    return engine


def _build_test_app(
    session_maker: async_sessionmaker[AsyncSession],
    ctx: OrganizationContext,
) -> FastAPI:
    app = FastAPI()
    api_v1 = APIRouter(prefix="/api/v1")
    api_v1.include_router(silos_router)
    app.include_router(api_v1)

    async def _override_get_session() -> AsyncSession:
        async with session_maker() as session:
            yield session

    async def _override_require_org_admin() -> OrganizationContext:
        return ctx

    app.dependency_overrides[get_session] = _override_get_session
    app.dependency_overrides[require_org_admin] = _override_require_org_admin
    return app


async def _seed_org_context(
    session: AsyncSession,
) -> tuple[OrganizationContext, Gateway]:
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
async def test_create_and_get_persisted_silo_via_api() -> None:
    engine = await _make_engine()
    session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_maker() as session:
        ctx, gateway = await _seed_org_context(session)
    app = _build_test_app(session_maker, ctx)

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            create_response = await client.post(
                "/api/v1/silos",
                json={
                    "name": "Demo Silo",
                    "blueprint_slug": "default-four-agent",
                    "gateway_assignments": [
                        {
                            "role_slug": "fox",
                            "gateway_id": str(gateway.id),
                            "workspace_root": "/srv/fox",
                        },
                    ],
                },
            )
            get_response = await client.get("/api/v1/silos/demo-silo")

        assert create_response.status_code == 201
        assert create_response.json()["slug"] == "demo-silo"
        assert create_response.json()["role_count"] == 4
        assert get_response.status_code == 200
        assert get_response.json()["name"] == "Demo Silo"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_list_silos_via_api_returns_persisted_items() -> None:
    engine = await _make_engine()
    session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_maker() as session:
        ctx, _ = await _seed_org_context(session)
    app = _build_test_app(session_maker, ctx)

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            await client.post(
                "/api/v1/silos",
                json={"name": "Demo Silo", "blueprint_slug": "default-four-agent"},
            )
            response = await client.get("/api/v1/silos")

        assert response.status_code == 200
        assert len(response.json()) == 1
        assert response.json()[0]["slug"] == "demo-silo"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_create_silo_via_api_returns_404_for_unknown_gateway() -> None:
    engine = await _make_engine()
    session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_maker() as session:
        ctx, _ = await _seed_org_context(session)
    app = _build_test_app(session_maker, ctx)

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            response = await client.post(
                "/api/v1/silos",
                json={
                    "name": "Broken Silo",
                    "blueprint_slug": "default-four-agent",
                    "gateway_assignments": [
                        {
                            "role_slug": "fox",
                            "gateway_id": str(uuid4()),
                        },
                    ],
                },
            )

        assert response.status_code == 404
        assert "Unknown gateway id" in response.json()["detail"]
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_patch_silo_via_api_updates_gateway_assignment() -> None:
    engine = await _make_engine()
    session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_maker() as session:
        ctx, gateway = await _seed_org_context(session)
    app = _build_test_app(session_maker, ctx)

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            create_response = await client.post(
                "/api/v1/silos",
                json={"name": "Demo Silo", "blueprint_slug": "default-four-agent"},
            )
            assert create_response.status_code == 201

            patch_response = await client.patch(
                "/api/v1/silos/demo-silo",
                json={
                    "gateway_assignments": [
                        {
                            "role_slug": "fox",
                            "gateway_id": str(gateway.id),
                            "workspace_root": "/srv/fox",
                        },
                    ],
                },
            )

        assert patch_response.status_code == 200
        body = patch_response.json()
        fox = next(role for role in body["roles"] if role["slug"] == "fox")
        assert fox["gateway_id"] == str(gateway.id)
        assert fox["gateway_name"] == "Fox Host"
        assert fox["workspace_root"] == "/srv/fox"
    finally:
        await engine.dispose()
